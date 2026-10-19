from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from cartoes.models import Parcela
from core.espacos import (
    filtrar_no_espaco,
    sala_ativa,
    sala_do_usuario,
    usuario_pode_administrar,
)
from core.periodos import (
    filtrar_saidas_por_referencia,
    limites_do_mes,
    mes_de_referencia,
)

from .forms import FiltroSaidaForm, PagamentoSaidaForm, SaidaForm
from .models import Saida
from .services import atualizar_saida, criar_saida, excluir_saida, marcar_saida_como_paga


def _saida_visivel(request, saida_id):
    return get_object_or_404(
        filtrar_no_espaco(
            Saida.objects.select_related("responsavel", "conta", "sala"), request
        ),
        pk=saida_id,
    )


def _dados_saida(form):
    campos = [
        "descricao", "valor", "responsavel", "custo_vida", "situacao",
        "vencimento", "data_pagamento", "forma_pagamento", "conta", "observacao",
    ]
    dados = {
        campo: form.cleaned_data.get(campo, getattr(form.instance, campo))
        for campo in campos
    }
    if dados["situacao"] == Saida.Situacao.PENDENTE:
        dados.update({"data_pagamento": None, "forma_pagamento": "", "conta": None})
    elif dados["situacao"] == Saida.Situacao.CANCELADA:
        dados["vencimento"] = (
            dados.get("vencimento") or dados.get("data_pagamento")
        )
        dados.update({"data_pagamento": None, "forma_pagamento": "", "conta": None})
    elif not form.instance.pk:
        dados.update({"forma_pagamento": "", "conta": None})
    return dados


def _sala_compartilhada(request, form):
    if sala_ativa(request) or not form.cleaned_data.get("compartilhar_sala"):
        return None
    return sala_do_usuario(request.user)


def _avisar_saldo_negativo(request, saida):
    if saida.situacao == Saida.Situacao.PAGA and saida.conta and saida.conta.saldo_atual < 0:
        messages.warning(request, f"Pagamento registrado. O saldo de {saida.conta.nome} ficou negativo.")


def _parametros_da_lista(request, mes):
    parametros = {"mes": mes}
    for nome in ("responsavel", "situacao", "custo_vida"):
        if request.GET.get(nome):
            parametros[nome] = request.GET[nome]
    return urlencode(parametros)


def _url_da_lista(request):
    if not request.GET:
        return reverse("saidas:lista")
    mes, _, _ = mes_de_referencia(request.GET.get("mes"))
    return f"{reverse('saidas:lista')}?{_parametros_da_lista(request, mes)}"


def _aplicar_filtros(queryset, form, inicio, fim):
    if not form.is_valid():
        return queryset
    queryset = filtrar_saidas_por_referencia(queryset, inicio, fim)
    if form.cleaned_data.get("responsavel"):
        queryset = queryset.filter(responsavel=form.cleaned_data["responsavel"])
    if form.cleaned_data.get("situacao"):
        queryset = queryset.filter(situacao=form.cleaned_data["situacao"])
    return queryset


@login_required
def lista(request):
    sala = sala_ativa(request)
    mes, ano, numero_mes = mes_de_referencia(request.GET.get("mes"))
    inicio, fim = limites_do_mes(ano, numero_mes)
    parametros = request.GET.copy()
    parametros["mes"] = mes
    filtro = FiltroSaidaForm(parametros, sala=sala, usuario=request.user)
    saidas = _aplicar_filtros(
        filtrar_no_espaco(
            Saida.objects.select_related("responsavel", "conta", "proprietario_usuario", "sala", "atalho"),
            request,
        ),
        filtro,
        inicio,
        fim,
    )
    somente_custo_vida = request.GET.get("custo_vida") == "1"
    if somente_custo_vida:
        saidas = saidas.filter(custo_vida=True).exclude(
            situacao=Saida.Situacao.CANCELADA
        )
    custos = saidas.filter(custo_vida=True)
    total_pago = custos.filter(situacao=Saida.Situacao.PAGA).aggregate(total=Sum("valor"))["total"] or Decimal("0.00")
    total_pendente = custos.filter(situacao=Saida.Situacao.PENDENTE).aggregate(total=Sum("valor"))["total"] or Decimal("0.00")

    parcelas_custo = Parcela.objects.filter(compra__custo_vida=True)
    # Parcela recebe a propriedade por meio da compra.
    if sala:
        parcelas_custo = parcelas_custo.filter(
            Q(compra__sala=sala)
            | Q(
                compra__sala_compartilhada=sala,
                compra__proprietario_usuario__vinculo_sala__sala=sala,
            )
        )
    else:
        parcelas_custo = parcelas_custo.filter(compra__proprietario_usuario=request.user)
    if filtro.is_valid():
        parcelas_custo = parcelas_custo.filter(
            fatura__ano_referencia=ano,
            fatura__mes_referencia=numero_mes,
        )
        if filtro.cleaned_data.get("responsavel"):
            parcelas_custo = parcelas_custo.filter(compra__responsavel=filtro.cleaned_data["responsavel"])
        if filtro.cleaned_data.get("situacao") == Saida.Situacao.PAGA:
            parcelas_custo = parcelas_custo.filter(fatura__pagamento__isnull=False)
        elif filtro.cleaned_data.get("situacao") == Saida.Situacao.PENDENTE:
            parcelas_custo = parcelas_custo.filter(fatura__pagamento__isnull=True)
    total_cartao = parcelas_custo.aggregate(total=Sum("valor"))["total"] or Decimal("0.00")

    parametros_navegacao = _parametros_da_lista(request, mes)
    return render(request, "saidas/lista.html", {
        "sala": sala,
        "titulo_espaco": sala.nome if sala else "Meu espaço",
        "contexto_espaco": sala.nome if sala else "Pessoal",
        "data_mes": inicio,
        "mes_selecionado": mes,
        "parametros_navegacao": parametros_navegacao,
        "voltar_url": f"{reverse('saidas:lista')}?{parametros_navegacao}",
        "saidas": Paginator(saidas, 10).get_page(request.GET.get("page")),
        "filtro": filtro,
        "total_custo_pago": total_pago,
        "total_custo_pendente": total_pendente,
        "total_custo_cartao": total_cartao,
        "somente_custo_vida": somente_custo_vida,
    })


@login_required
def criar(request):
    sala = sala_ativa(request)
    form = SaidaForm(request.POST or None, sala=sala, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        saida, foi_criada = criar_saida(
            sala=sala,
            proprietario_usuario=None if sala else request.user,
            autor=request.user,
            sala_compartilhada=_sala_compartilhada(request, form),
            chave_idempotencia=form.cleaned_data["chave_formulario"],
            dados=_dados_saida(form),
        )
        if foi_criada:
            messages.success(request, "Saída registrada com sucesso.")
            _avisar_saldo_negativo(request, saida)
        else:
            messages.info(request, "Este formulário já havia sido processado.")
        return redirect(_url_da_lista(request))
    return render(request, "saidas/formulario.html", {
        "form": form,
        "titulo": "Registrar saída",
        "texto_botao": "Registrar saída",
        "voltar_url": _url_da_lista(request),
    })


@login_required
def editar(request, saida_id):
    sala = sala_ativa(request)
    saida = _saida_visivel(request, saida_id)
    if not usuario_pode_administrar(saida, request.user):
        raise Http404
    form = SaidaForm(request.POST or None, instance=saida, sala=sala, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        dados = _dados_saida(form)
        if saida.proprietario_usuario_id and "compartilhar_sala" in form.fields:
            dados["sala_compartilhada"] = _sala_compartilhada(request, form)
        saida_atualizada = atualizar_saida(saida, dados)
        messages.success(request, "Saída atualizada e saldo corrigido.")
        _avisar_saldo_negativo(request, saida_atualizada)
        return redirect(_url_da_lista(request))
    return render(request, "saidas/formulario.html", {
        "form": form,
        "titulo": "Editar saída",
        "texto_botao": "Salvar alterações",
        "voltar_url": _url_da_lista(request),
    })


@login_required
def excluir(request, saida_id):
    saida = _saida_visivel(request, saida_id)
    if not usuario_pode_administrar(saida, request.user):
        raise Http404
    if request.method == "POST":
        excluir_saida(saida)
        messages.success(request, "Saída excluída e saldo corrigido.")
        return redirect(_url_da_lista(request))
    return render(request, "saidas/confirmar_exclusao.html", {
        "saida": saida,
        "voltar_url": _url_da_lista(request),
    })


@login_required
def pagar(request, saida_id):
    sala = sala_ativa(request)
    saida = _saida_visivel(request, saida_id)
    if not usuario_pode_administrar(saida, request.user):
        raise Http404
    if saida.situacao != Saida.Situacao.PENDENTE:
        messages.info(request, "Somente uma saída a pagar pode ser confirmada.")
        return redirect(_url_da_lista(request))

    form = PagamentoSaidaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        saida_paga, foi_alterada = marcar_saida_como_paga(
            saida=saida,
            data_pagamento=form.cleaned_data["data_pagamento"],
            forma_pagamento="",
            conta=None,
        )
        if foi_alterada:
            messages.success(request, "Pagamento registrado com sucesso.")
            _avisar_saldo_negativo(request, saida_paga)
        else:
            messages.info(request, "Esta saída já havia sido paga.")
        return redirect(_url_da_lista(request))
    return render(request, "saidas/pagar.html", {
        "saida": saida,
        "form": form,
        "voltar_url": _url_da_lista(request),
    })
