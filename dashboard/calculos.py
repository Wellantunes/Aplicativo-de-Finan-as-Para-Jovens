from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from cartoes.models import Fatura, PagamentoFatura, Parcela
from contas.models import CartaoCredito, Conta
from core.periodos import (
    filtrar_entradas_por_referencia,
    filtrar_saidas_por_referencia,
)
from entradas.models import DevolucaoDizimo, Entrada
from saidas.models import Saida


ZERO = Decimal("0.00")


def somar(queryset, campo="valor"):
    return queryset.aggregate(total=Sum(campo))["total"] or ZERO


def periodo_do_mes(ano, mes):
    inicio = date(ano, mes, 1)
    fim = date(ano, mes, monthrange(ano, mes)[1])
    hoje = timezone.localdate()
    if fim < hoje:
        return inicio, fim, fim, "fechamento"
    if inicio > hoje:
        return inicio, fim, fim, "previsao"
    return inicio, fim, hoje, "atual"


def _propriedade(sala, usuario, prefixo="", somente_sala=False):
    campo_sala = f"{prefixo}sala"
    campo_usuario = f"{prefixo}proprietario_usuario"
    campo_compartilhada = f"{prefixo}sala_compartilhada"
    if sala:
        if somente_sala:
            return Q(**{campo_sala: sala})
        campo_membro = f"{prefixo}proprietario_usuario__vinculo_sala__sala"
        return Q(**{campo_sala: sala}) | Q(
            **{
                campo_compartilhada: sala,
                campo_membro: sala,
            }
        )
    return Q(**{campo_usuario: usuario})


def _filtrar_responsavel(queryset, responsavel, campo):
    return queryset.filter(**{campo: responsavel}) if responsavel else queryset


def _totais_por_conta(queryset, campo_conta):
    """Agrupa valores por conta em uma única consulta."""

    return {
        conta_id: total
        for conta_id, total in queryset.values(campo_conta)
        .annotate(total=Sum("valor"))
        .values_list(campo_conta, "total")
    }


def _saldos_contas_na_data(contas, referencia):
    """Calcula todos os saldos sem repetir consultas para cada conta."""

    contas = list(contas)
    contas_ids = [conta.pk for conta in contas]
    entradas = _totais_por_conta(
        Entrada.objects.filter(
            conta_destino_id__in=contas_ids,
            situacao=Entrada.Situacao.RECEBIDA,
            data__lte=referencia,
        ),
        "conta_destino_id",
    )
    dizimos = _totais_por_conta(
        DevolucaoDizimo.objects.filter(
            conta_id__in=contas_ids,
            data__lte=referencia,
        ),
        "conta_id",
    )
    saidas = _totais_por_conta(
        Saida.objects.filter(
            conta_id__in=contas_ids,
            situacao=Saida.Situacao.PAGA,
            data_pagamento__lte=referencia,
        ),
        "conta_id",
    )
    faturas = _totais_por_conta(
        PagamentoFatura.objects.filter(
            conta_id__in=contas_ids,
            data_pagamento__lte=referencia,
        ),
        "conta_id",
    )

    saldos = []
    for conta in contas:
        saldo = conta.saldo_inicial if conta.data_saldo_inicial <= referencia else ZERO
        saldo += entradas.get(conta.pk, ZERO)
        saldo -= dizimos.get(conta.pk, ZERO)
        saldo -= saidas.get(conta.pk, ZERO)
        saldo -= faturas.get(conta.pk, ZERO)
        saldos.append({"conta": conta, "saldo": saldo})
    return saldos


def _total_dizimo_pendente(entradas, referencia):
    campo_decimal = DecimalField(max_digits=12, decimal_places=2)
    entradas_com_devolucoes = entradas.annotate(
        devolvido_ate_referencia=Coalesce(
            Sum(
                "devolucoes__valor",
                filter=Q(devolucoes__data__lte=referencia),
            ),
            Value(ZERO),
            output_field=campo_decimal,
        )
    )
    return sum(
        (
            max(
                entrada.dizimo_previsto - entrada.devolvido_ate_referencia,
                ZERO,
            )
            for entrada in entradas_com_devolucoes
        ),
        ZERO,
    )


def _faturas_disponiveis(sala, usuario, somente_sala=False):
    cartoes = CartaoCredito.objects.filter(
        _propriedade(sala, usuario, somente_sala=somente_sala)
    )
    return Fatura.objects.filter(cartao__in=cartoes)


def _parcelas_visiveis(sala, usuario, somente_sala=False):
    return Parcela.objects.filter(
        _propriedade(
            sala,
            usuario,
            prefixo="compra__",
            somente_sala=somente_sala,
        )
    )


def _resumo_faturas(sala, usuario, ano, mes, referencia, responsavel, somente_sala):
    faturas = list(
        _faturas_disponiveis(sala, usuario, somente_sala)
        .filter(
            ano_referencia=ano,
            mes_referencia=mes,
        )
        .select_related("cartao", "pagamento")
    )
    faturas_ids = [fatura.pk for fatura in faturas]
    totais_reais = {
        fatura_id: total
        for fatura_id, total in Parcela.objects.filter(fatura_id__in=faturas_ids)
        .values("fatura_id")
        .annotate(total=Sum("valor"))
        .values_list("fatura_id", "total")
    }
    parcelas_permitidas = _parcelas_visiveis(
        sala,
        usuario,
        somente_sala,
    ).filter(fatura_id__in=faturas_ids)
    parcelas_permitidas = _filtrar_responsavel(
        parcelas_permitidas,
        responsavel,
        "compra__responsavel",
    )
    subtotais_visiveis = {
        fatura_id: total
        for fatura_id, total in parcelas_permitidas.values("fatura_id")
        .annotate(total=Sum("valor"))
        .values_list("fatura_id", "total")
    }
    resumo = []
    for fatura in faturas:
        subtotal = subtotais_visiveis.get(fatura.pk, ZERO)
        if subtotal == ZERO and responsavel:
            continue
        valor_total_real = totais_reais.get(fatura.pk, ZERO)
        resumo.append({
            "fatura": fatura,
            "valor": subtotal,
            "valor_total_real": valor_total_real,
            "possui_itens_privados": subtotal != valor_total_real,
            "paga": fatura.esta_paga and fatura.pagamento.data_pagamento <= referencia,
        })
    return resumo


def calcular_dashboard(
    sala,
    ano,
    mes,
    responsavel=None,
    usuario=None,
    somente_sala=False,
):
    # A assinatura antiga continua válida para os registros históricos da sala.
    if usuario is None and sala is not None:
        usuario = sala.criado_por
    inicio, fim, referencia, tipo_periodo = periodo_do_mes(ano, mes)
    propriedade = _propriedade(sala, usuario, somente_sala=somente_sala)
    controla_dizimos = (
        sala.controlar_dizimos if sala else bool(usuario and usuario.dizimo_automatico)
    )

    contas = Conta.objects.filter(propriedade).select_related("titular").distinct()
    if responsavel:
        contas = contas.filter(titular=responsavel)
    saldos_contas = _saldos_contas_na_data(contas, referencia)
    saldos_dinheiro_contas = [item for item in saldos_contas if item["conta"].tipo == Conta.Tipo.DINHEIRO]
    saldos_vale_contas = [item for item in saldos_contas if item["conta"].tipo == Conta.Tipo.VALE_ALIMENTACAO]
    saldo_dinheiro = sum((item["saldo"] for item in saldos_dinheiro_contas), ZERO)
    saldo_vale = sum((item["saldo"] for item in saldos_vale_contas), ZERO)

    entradas_base = Entrada.objects.filter(propriedade)
    entradas_mes = _filtrar_responsavel(
        filtrar_entradas_por_referencia(
            entradas_base.exclude(situacao=Entrada.Situacao.CANCELADA),
            inicio,
            fim,
        ).select_related("conta_destino", "pessoa"),
        responsavel,
        "pessoa",
    )
    entradas_dinheiro = somar(entradas_mes.exclude(tipo="vale_alimentacao"))
    vale_mes = somar(entradas_mes.filter(tipo="vale_alimentacao"))
    # O total de entradas apresenta tudo o que entrou no mes. O resultado
    # financeiro continua usando somente dinheiro, pois vale e um beneficio.
    total_entradas_mes = entradas_dinheiro + vale_mes
    dizimo_previsto = somar(entradas_mes, "dizimo_previsto")

    devolucoes_mes = DevolucaoDizimo.objects.filter(
        _propriedade(sala, usuario, prefixo="entrada__", somente_sala=somente_sala),
        data__range=(inicio, referencia),
    )
    devolucoes_mes = _filtrar_responsavel(devolucoes_mes, responsavel, "entrada__pessoa")
    if inicio > timezone.localdate():
        devolucoes_mes = devolucoes_mes.none()
    dizimo_devolvido = somar(devolucoes_mes)
    dizimo_pendente_mes = _total_dizimo_pendente(entradas_mes, referencia)

    saidas_base = Saida.objects.filter(propriedade)
    saidas_mes = _filtrar_responsavel(
        filtrar_saidas_por_referencia(
            saidas_base.exclude(situacao=Saida.Situacao.CANCELADA),
            inicio,
            fim,
        ),
        responsavel,
        "responsavel",
    )
    saidas_pagas = _filtrar_responsavel(
        saidas_base.filter(situacao=Saida.Situacao.PAGA, data_pagamento__range=(inicio, referencia)),
        responsavel,
        "responsavel",
    )
    if inicio > timezone.localdate():
        saidas_pagas = saidas_pagas.none()

    parcelas_mes = _parcelas_visiveis(sala, usuario, somente_sala).filter(
        fatura__ano_referencia=ano,
        fatura__mes_referencia=mes,
    )
    parcelas_mes = _filtrar_responsavel(parcelas_mes, responsavel, "compra__responsavel")

    custo_vida = somar(saidas_mes.filter(custo_vida=True)) + somar(
        parcelas_mes.filter(compra__custo_vida=True)
    )
    outros_gastos = somar(saidas_mes.filter(custo_vida=False)) + somar(
        parcelas_mes.filter(compra__custo_vida=False)
    )

    pagamentos_fatura_mes = PagamentoFatura.objects.filter(
        fatura__in=_faturas_disponiveis(sala, usuario, somente_sala),
        data_pagamento__range=(inicio, referencia),
        conta__isnull=False,
    )
    if responsavel:
        valor_faturas_pagas = somar(
            _parcelas_visiveis(sala, usuario, somente_sala).filter(
                fatura__pagamento__in=pagamentos_fatura_mes,
                compra__responsavel=responsavel,
            )
        )
    else:
        valor_faturas_pagas = somar(pagamentos_fatura_mes)
    saidas_dinheiro = somar(
        saidas_pagas.filter(
            Q(conta__isnull=True) | Q(conta__tipo=Conta.Tipo.DINHEIRO)
        )
    ) + dizimo_devolvido + valor_faturas_pagas
    saidas_vale_mes = somar(
        saidas_mes.filter(
            Q(conta__tipo=Conta.Tipo.VALE_ALIMENTACAO)
            | Q(forma_pagamento=Saida.FormaPagamento.VALE_ALIMENTACAO)
        )
    )
    saidas_dinheiro_mes = somar(saidas_mes) - saidas_vale_mes
    total_saidas_mes = saidas_dinheiro_mes + somar(parcelas_mes) + dizimo_devolvido
    resultado_mes = entradas_dinheiro - total_saidas_mes

    saidas_pendentes_ate_fim = _filtrar_responsavel(
        saidas_base.filter(vencimento__lte=fim).filter(
            Q(situacao=Saida.Situacao.PENDENTE)
            | Q(situacao=Saida.Situacao.PAGA, data_pagamento__gt=referencia)
        ),
        responsavel,
        "responsavel",
    )
    compromissos_saidas = somar(saidas_pendentes_ate_fim)

    faturas_pendentes = _faturas_disponiveis(sala, usuario, somente_sala).filter(
        data_vencimento__lte=fim
    ).filter(Q(pagamento__isnull=True) | Q(pagamento__data_pagamento__gt=referencia))
    parcelas_pendentes = _parcelas_visiveis(sala, usuario, somente_sala).filter(fatura__in=faturas_pendentes)
    parcelas_pendentes = _filtrar_responsavel(parcelas_pendentes, responsavel, "compra__responsavel")
    compromissos_faturas = somar(parcelas_pendentes)

    entradas_ate_referencia = _filtrar_responsavel(
        entradas_base.filter(
            situacao=Entrada.Situacao.RECEBIDA,
            data__lte=referencia,
        ),
        responsavel,
        "pessoa",
    )
    compromissos_dizimo = (
        _total_dizimo_pendente(entradas_ate_referencia, referencia)
        if controla_dizimos
        else ZERO
    )
    compromissos_dinheiro = compromissos_saidas + compromissos_faturas + compromissos_dizimo

    limite_proximas = min(fim, referencia + timedelta(days=7))
    compromissos_lista = saidas_pendentes_ate_fim.filter(
        vencimento__lte=limite_proximas
    ).select_related("responsavel").order_by("vencimento")

    orcamento = sala.orcamento_mensal if sala else usuario.orcamento_mensal_individual
    if sala and somente_sala:
        renda_prevista = ZERO
    elif sala and responsavel:
        renda_prevista = responsavel.renda_mensal_prevista or ZERO
    elif sala:
        renda_prevista = sum(
            (membro.usuario.renda_mensal_prevista or ZERO)
            for membro in sala.membros.select_related("usuario").all()
        )
    else:
        renda_prevista = usuario.renda_mensal_prevista or ZERO

    return {
        "ano": ano, "mes": mes, "inicio": inicio, "fim": fim,
        "referencia": referencia, "tipo_periodo": tipo_periodo,
        "responsavel": responsavel, "somente_sala": somente_sala,
        "controla_dizimos": controla_dizimos,
        "renda_prevista": renda_prevista,
        "total_entradas_mes": total_entradas_mes,
        "total_saidas_mes": total_saidas_mes,
        "resultado_mes": resultado_mes,
        "mes_em_deficit": resultado_mes < ZERO,
        "entradas_dinheiro": entradas_dinheiro, "vale_mes": vale_mes,
        "saidas_vale_mes": saidas_vale_mes,
        "dizimo_previsto": dizimo_previsto, "dizimo_devolvido": dizimo_devolvido,
        "dizimo_pendente": dizimo_pendente_mes,
        "custo_vida": custo_vida,
        "outros_gastos": outros_gastos,
        "saidas_dinheiro": saidas_dinheiro,
        "saldo_dinheiro": saldo_dinheiro, "saldo_vale": saldo_vale,
        "saldos_contas": saldos_contas,
        "saldos_dinheiro_contas": saldos_dinheiro_contas,
        "saldos_vale_contas": saldos_vale_contas,
        "compromissos_saidas": compromissos_saidas,
        "compromissos_faturas": compromissos_faturas,
        "compromissos_dizimo": compromissos_dizimo,
        "compromissos_dinheiro": compromissos_dinheiro,
        "disponivel_apos_compromissos": saldo_dinheiro - compromissos_dinheiro,
        "orcamento_custo_vida": orcamento,
        "orcamento_restante": orcamento - custo_vida,
        "compromissos_lista": compromissos_lista,
        "faturas_resumo": _resumo_faturas(
            sala, usuario, ano, mes, referencia, responsavel, somente_sala
        ),
    }
