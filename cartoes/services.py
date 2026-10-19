from decimal import Decimal

from django.db import transaction
from django.contrib.auth import get_user_model

from contas.models import CartaoCredito
from salas.models import Sala

from .models import CompraCredito, Fatura, PagamentoFatura, Parcela


class CartaoErro(Exception):
    """Erro esperado ao alterar compras ou faturas."""


def adicionar_meses(ano, mes, quantidade):
    indice = ano * 12 + (mes - 1) + quantidade
    return indice // 12, indice % 12 + 1


def referencia_primeiro_fechamento(cartao, data_compra):
    """Retorna o ciclo de fechamento que receberá a primeira parcela."""

    fechamento = cartao.data_fechamento_no_mes(data_compra.year, data_compra.month)
    if data_compra <= fechamento:
        return data_compra.year, data_compra.month
    return adicionar_meses(data_compra.year, data_compra.month, 1)


def datas_da_fatura(cartao, ano, mes):
    fechamento = cartao.data_fechamento_no_mes(ano, mes)
    ano_vencimento, mes_vencimento = ano, mes
    vencimento = cartao.data_vencimento_no_mes(ano_vencimento, mes_vencimento)
    if vencimento <= fechamento:
        ano_vencimento, mes_vencimento = adicionar_meses(ano, mes, 1)
        vencimento = cartao.data_vencimento_no_mes(
            ano_vencimento,
            mes_vencimento,
        )
    return fechamento, vencimento


def prever_fatura_da_compra(cartao, data_compra):
    """Calcula o ciclo sem criar ou alterar registros no banco."""

    existente_por_fechamento = (
        Fatura.objects.filter(cartao=cartao, data_fechamento__gte=data_compra)
        .order_by("data_fechamento")
        .first()
    )
    if existente_por_fechamento and (
        existente_por_fechamento.data_fechamento - data_compra
    ).days <= 31:
        return (
            existente_por_fechamento.data_fechamento,
            existente_por_fechamento.data_vencimento,
            existente_por_fechamento,
        )

    ano, mes = referencia_primeiro_fechamento(cartao, data_compra)
    fechamento, vencimento = datas_da_fatura(cartao, ano, mes)
    existente = Fatura.objects.filter(
        cartao=cartao,
        ano_referencia=vencimento.year,
        mes_referencia=vencimento.month,
    ).first()
    if existente:
        return existente.data_fechamento, existente.data_vencimento, existente
    return fechamento, vencimento, None


def distribuir_centavos(valor_total, quantidade):
    total_centavos = int(valor_total * 100)
    valor_base, centavos_restantes = divmod(total_centavos, quantidade)
    return [
        Decimal(valor_base + (1 if indice < centavos_restantes else 0)) / 100
        for indice in range(quantidade)
    ]


def _obter_fatura(cartao, ano_fechamento, mes_fechamento):
    fechamento, vencimento = datas_da_fatura(
        cartao,
        ano_fechamento,
        mes_fechamento,
    )
    fatura, _ = Fatura.objects.get_or_create(
        cartao=cartao,
        ano_referencia=vencimento.year,
        mes_referencia=vencimento.month,
        defaults={
            "data_fechamento": fechamento,
            "data_vencimento": vencimento,
        },
    )
    return fatura


def _gerar_parcelas(compra, fatura_destino=None):
    if fatura_destino:
        if compra.quantidade_parcelas != 1:
            raise CartaoErro("A escolha manual de fatura aceita uma única parcela.")
        Parcela.objects.create(
            compra=compra,
            fatura=fatura_destino,
            numero=1,
            valor=compra.valor_total,
        )
        return

    ano_fechamento, mes_fechamento = referencia_primeiro_fechamento(
        compra.cartao,
        compra.data_compra,
    )
    valores = distribuir_centavos(compra.valor_total, compra.quantidade_parcelas)
    for indice, valor in enumerate(valores):
        ano, mes = adicionar_meses(ano_fechamento, mes_fechamento, indice)
        if indice == 0:
            _, _, fatura_existente = prever_fatura_da_compra(
                compra.cartao,
                compra.data_compra,
            )
        else:
            fatura_existente = None
        fatura = fatura_existente or _obter_fatura(compra.cartao, ano, mes)
        if fatura.esta_paga:
            raise CartaoErro(
                "A fatura de destino já está paga. Escolha uma fatura aberta."
            )
        Parcela.objects.create(
            compra=compra,
            fatura=fatura,
            numero=indice + 1,
            valor=valor,
        )


def _remover_parcelas_nao_pagas(compra):
    if compra.parcelas.filter(fatura__pagamento__isnull=False).exists():
        raise CartaoErro(
            "Esta compra pertence a uma fatura paga e não pode ser alterada nesta versão."
        )
    faturas = list(compra.parcelas.values_list("fatura_id", flat=True))
    compra.parcelas.all().delete()
    Fatura.objects.filter(
        pk__in=faturas,
        parcelas__isnull=True,
        pagamento__isnull=True,
    ).delete()


@transaction.atomic
def criar_compra(
    sala,
    chave_idempotencia,
    dados,
    proprietario_usuario=None,
    autor=None,
    sala_compartilhada=None,
    fatura_destino=None,
):
    if sala:
        Sala.objects.select_for_update().get(pk=sala.pk)
    elif proprietario_usuario:
        get_user_model().objects.select_for_update().get(pk=proprietario_usuario.pk)
    existente = CompraCredito.objects.filter(
        chave_idempotencia=chave_idempotencia
    ).first()
    if existente:
        return existente, False

    cartao = CartaoCredito.objects.select_for_update().get(pk=dados["cartao"].pk)
    if cartao.arquivado:
        raise CartaoErro("Este cartão está arquivado e não aceita novas compras.")
    if fatura_destino:
        fatura_destino = Fatura.objects.select_for_update().filter(
            pk=fatura_destino.pk,
            cartao=cartao,
            pagamento__isnull=True,
        ).first()
        if not fatura_destino:
            raise CartaoErro("Escolha uma fatura aberta deste mesmo cartão.")
    dados = {**dados, "cartao": cartao}
    compra = CompraCredito(
        sala=sala,
        proprietario_usuario=proprietario_usuario,
        sala_compartilhada=sala_compartilhada,
        autor=autor,
        chave_idempotencia=chave_idempotencia,
        **dados,
    )
    compra.full_clean()
    compra.save()
    _gerar_parcelas(compra, fatura_destino=fatura_destino)
    return compra, True


@transaction.atomic
def atualizar_compra(compra, dados):
    compra_bloqueada = CompraCredito.objects.select_for_update().get(pk=compra.pk)
    _remover_parcelas_nao_pagas(compra_bloqueada)
    cartao = CartaoCredito.objects.select_for_update().get(pk=dados["cartao"].pk)
    dados = {**dados, "cartao": cartao}
    for campo, valor in dados.items():
        setattr(compra_bloqueada, campo, valor)
    compra_bloqueada.full_clean()
    compra_bloqueada.save()
    _gerar_parcelas(compra_bloqueada)
    return compra_bloqueada


@transaction.atomic
def excluir_compra(compra):
    compra_bloqueada = CompraCredito.objects.select_for_update().get(pk=compra.pk)
    _remover_parcelas_nao_pagas(compra_bloqueada)
    compra_bloqueada.delete()


@transaction.atomic
def pagar_fatura(fatura, conta, data_pagamento, usuario):
    fatura_bloqueada = Fatura.objects.select_for_update().get(pk=fatura.pk)
    pagamento_existente = PagamentoFatura.objects.filter(
        fatura=fatura_bloqueada
    ).first()
    if pagamento_existente:
        return pagamento_existente, False

    valor = fatura_bloqueada.valor_total
    if valor <= 0:
        raise CartaoErro("Esta fatura não possui parcelas para pagamento.")

    pagamento = PagamentoFatura(
        fatura=fatura_bloqueada,
        conta=conta,
        valor=valor,
        data_pagamento=data_pagamento,
        registrado_por=usuario,
    )
    pagamento.full_clean()
    pagamento.save()
    return pagamento, True


@transaction.atomic
def atualizar_datas_fatura(fatura, data_fechamento, data_vencimento):
    fatura_bloqueada = Fatura.objects.select_for_update().get(pk=fatura.pk)
    if fatura_bloqueada.esta_paga:
        raise CartaoErro("Uma fatura paga não pode ter suas datas alteradas.")
    fatura_bloqueada.data_fechamento = data_fechamento
    fatura_bloqueada.data_vencimento = data_vencimento
    fatura_bloqueada.ano_referencia = data_vencimento.year
    fatura_bloqueada.mes_referencia = data_vencimento.month
    fatura_bloqueada.full_clean()
    fatura_bloqueada.save(
        update_fields=[
            "data_fechamento",
            "data_vencimento",
            "ano_referencia",
            "mes_referencia",
        ]
    )
    return fatura_bloqueada
