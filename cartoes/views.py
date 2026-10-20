from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from contas.models import CartaoCredito
from core.espacos import (
    filtro_do_espaco,
    recursos_disponiveis,
    sala_ativa,
    sala_do_usuario,
    usuario_pode_administrar,
)
from core.periodos import data_inicial_do_mes, mes_ativo

from .forms import (
    CompraCreditoForm,
    CompraRapidaCartaoForm,
    FaturaDatasForm,
    PagamentoFaturaForm,
)
from .models import CompraCredito, Fatura
from .services import (
    CartaoErro,
    atualizar_compra,
    atualizar_datas_fatura,
    criar_compra,
    excluir_compra,
    pagar_fatura,
    prever_fatura_da_compra,
)


def _compras_visiveis(request):
    return CompraCredito.objects.filter(filtro_do_espaco(request))


def _cartoes_visiveis(request, *, incluir_arquivados=True):
    cartoes = recursos_disponiveis(CartaoCredito.objects.all(), request)
    return cartoes if incluir_arquivados else cartoes.filter(arquivado=False)


def _cartao_visivel(request, cartao_id, *, incluir_arquivado=True):
    return get_object_or_404(
        _cartoes_visiveis(request, incluir_arquivados=incluir_arquivado),
        pk=cartao_id,
    )


def _dados_compra(form):
    campos = [
        "cartao",
        "responsavel",
        "descricao",
        "valor_total",
        "data_compra",
        "quantidade_parcelas",
        "custo_vida",
    ]
    return {campo: form.cleaned_data[campo] for campo in campos}


def _sala_compartilhada_form(request, form):
    if sala_ativa(request) or not form.cleaned_data.get("compartilhar_sala"):
        return None
    return sala_do_usuario(request.user)


def _sala_compartilhada_compra_rapida(request, cartao):
    if sala_ativa(request) or not request.user.compartilhar_novos_lancamentos:
        return None
    return cartao.sala_compartilhada


def _fatura_visivel(request, fatura_id):
    return get_object_or_404(
        Fatura.objects.select_related(
            "cartao", "cartao__proprietario_usuario", "pagamento__conta"
        ).prefetch_related("parcelas__compra__responsavel"),
        pk=fatura_id,
        cartao__in=_cartoes_visiveis(request),
    )


def _parcelas_visiveis(fatura, request):
    parcelas = fatura.parcelas.select_related("compra", "compra__responsavel")
    sala = sala_ativa(request)
    if sala:
        return parcelas.filter(
            Q(compra__sala=sala)
            | Q(
                compra__sala_compartilhada=sala,
                compra__proprietario_usuario__vinculo_sala__sala=sala,
            )
        )
    return parcelas.filter(compra__proprietario_usuario=request.user)


@login_required
def lista(request):
    mes_ativo(request, request.GET.get("mes"))
    cartoes = _cartoes_visiveis(request).select_related(
        "titular", "proprietario_usuario"
    )
    sala = sala_ativa(request)
    return render(
        request,
        "cartoes/lista.html",
        {
            "sala": sala,
            "titulo_espaco": sala.nome if sala else "Meu espaço",
            "cartoes": cartoes.filter(arquivado=False),
            "cartoes_arquivados": cartoes.filter(arquivado=True),
        },
    )


@login_required
def detalhe_cartao(request, cartao_id):
    cartao = _cartao_visivel(request, cartao_id)
    return render(
        request,
        "cartoes/detalhe_cartao.html",
        {
            "cartao": cartao,
            "faturas": cartao.faturas.select_related("pagamento").prefetch_related(
                "parcelas"
            ),
            "compras": _compras_visiveis(request)
            .filter(cartao=cartao)
            .select_related("responsavel")
            .prefetch_related("parcelas__fatura"),
            "pode_administrar": usuario_pode_administrar(cartao, request.user),
        },
    )


@login_required
@require_POST
def alternar_arquivo_cartao(request, cartao_id):
    cartao = _cartao_visivel(request, cartao_id)
    if not usuario_pode_administrar(cartao, request.user):
        raise Http404
    cartao.arquivado = not cartao.arquivado
    cartao.save(update_fields=["arquivado", "atualizado_em"])
    acao = "arquivado" if cartao.arquivado else "restaurado"
    messages.success(request, f"Cartão {acao}. O histórico foi preservado.")
    return redirect("cartoes:detalhe_cartao", cartao_id=cartao.pk)


@login_required
def criar_compra_cartao(request, cartao_id):
    cartao = _cartao_visivel(request, cartao_id, incluir_arquivado=False)
    _, ano, numero_mes = mes_ativo(request, request.GET.get("mes"))
    form = CompraRapidaCartaoForm(request.POST or None, cartao=cartao)
    if request.method == "GET":
        form.fields["data_compra"].initial = data_inicial_do_mes(ano, numero_mes)

    if request.method == "POST" and form.is_valid():
        sala = sala_ativa(request)
        dados = {
            "cartao": cartao,
            "responsavel": request.user,
            "descricao": form.cleaned_data["descricao"],
            "valor_total": form.cleaned_data["valor_total"],
            "data_compra": form.cleaned_data["data_compra"],
            "quantidade_parcelas": 1,
            "custo_vida": False,
        }
        try:
            compra, foi_criada = criar_compra(
                sala=sala,
                proprietario_usuario=None if sala else request.user,
                autor=request.user,
                sala_compartilhada=_sala_compartilhada_compra_rapida(
                    request, cartao
                ),
                chave_idempotencia=form.cleaned_data["chave_formulario"],
                dados=dados,
                fatura_destino=form.cleaned_data.get("fatura_destino"),
            )
        except CartaoErro as erro:
            form.add_error(None, str(erro))
        else:
            if foi_criada:
                messages.success(request, "Compra registrada com sucesso.")
            else:
                messages.info(request, "Este formulário já havia sido processado.")
            return redirect("cartoes:detalhe_cartao", cartao_id=compra.cartao_id)

    data_previa = form["data_compra"].value() or timezone.localdate().isoformat()
    try:
        data_previa = date.fromisoformat(str(data_previa))
    except ValueError:
        data_previa = timezone.localdate()
    fechamento, vencimento, _ = prever_fatura_da_compra(cartao, data_previa)
    return render(
        request,
        "cartoes/compra_rapida.html",
        {
            "cartao": cartao,
            "form": form,
            "fechamento_previa": fechamento,
            "vencimento_previa": vencimento,
        },
    )


@login_required
@require_GET
def previa_fatura(request, cartao_id):
    cartao = _cartao_visivel(request, cartao_id, incluir_arquivado=False)
    try:
        data_compra = date.fromisoformat(request.GET.get("data", ""))
    except ValueError:
        return JsonResponse({"erro": "Informe uma data válida."}, status=400)
    fechamento, vencimento, fatura = prever_fatura_da_compra(cartao, data_compra)
    return JsonResponse(
        {
            "fechamento": fechamento.strftime("%d/%m/%Y"),
            "vencimento": vencimento.strftime("%d/%m/%Y"),
            "fatura_id": fatura.pk if fatura else None,
        }
    )


# Compatibilidade com favoritos e formulários antigos. O fluxo visível usa o cartão.
@login_required
def criar_compra_view(request):
    sala = sala_ativa(request)
    _, ano, numero_mes = mes_ativo(request, request.GET.get("mes"))
    form = CompraCreditoForm(
        request.POST or None,
        sala=sala,
        usuario=request.user,
        initial={"data_compra": data_inicial_do_mes(ano, numero_mes)},
    )
    if request.method == "POST" and form.is_valid():
        compra, foi_criada = criar_compra(
            sala=sala,
            proprietario_usuario=None if sala else request.user,
            autor=request.user,
            sala_compartilhada=_sala_compartilhada_form(request, form),
            chave_idempotencia=form.cleaned_data["chave_formulario"],
            dados=_dados_compra(form),
        )
        if foi_criada:
            messages.success(request, "Compra e parcelas registradas com sucesso.")
        else:
            messages.info(request, "Este formulário já havia sido processado.")
        return redirect("cartoes:detalhe_cartao", cartao_id=compra.cartao_id)
    return render(
        request,
        "cartoes/formulario_compra.html",
        {"form": form, "titulo": "Registrar compra", "texto_botao": "Registrar compra"},
    )


@login_required
def editar_compra(request, compra_id):
    sala = sala_ativa(request)
    compra = get_object_or_404(_compras_visiveis(request), pk=compra_id)
    if not usuario_pode_administrar(compra, request.user):
        raise Http404
    if compra.parcelas.filter(fatura__pagamento__isnull=False).exists():
        messages.error(
            request,
            "Esta compra pertence a uma fatura paga e não pode ser editada nesta versão.",
        )
        return redirect("cartoes:detalhe_cartao", cartao_id=compra.cartao_id)

    form = CompraCreditoForm(
        request.POST or None, instance=compra, sala=sala, usuario=request.user
    )
    if request.method == "POST" and form.is_valid():
        dados = _dados_compra(form)
        if compra.proprietario_usuario_id and "compartilhar_sala" in form.fields:
            dados["sala_compartilhada"] = _sala_compartilhada_form(request, form)
        try:
            atualizar_compra(compra, dados)
        except CartaoErro as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Compra e parcelas atualizadas.")
        return redirect("cartoes:detalhe_cartao", cartao_id=compra.cartao_id)
    return render(
        request,
        "cartoes/formulario_compra.html",
        {"form": form, "titulo": "Editar compra", "texto_botao": "Salvar alterações"},
    )


@login_required
def excluir_compra_view(request, compra_id):
    compra = get_object_or_404(_compras_visiveis(request), pk=compra_id)
    if not usuario_pode_administrar(compra, request.user):
        raise Http404
    cartao_id = compra.cartao_id
    if request.method == "POST":
        try:
            excluir_compra(compra)
        except CartaoErro as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Compra e parcelas excluídas.")
        return redirect("cartoes:detalhe_cartao", cartao_id=cartao_id)
    return render(request, "cartoes/confirmar_exclusao.html", {"compra": compra})


@login_required
def detalhe_fatura(request, fatura_id):
    fatura = _fatura_visivel(request, fatura_id)
    parcelas_visiveis = _parcelas_visiveis(fatura, request)
    subtotal_visivel = parcelas_visiveis.aggregate(total=Sum("valor"))["total"] or 0
    pode_administrar = usuario_pode_administrar(fatura.cartao, request.user)
    return render(
        request,
        "cartoes/detalhe_fatura.html",
        {
            "fatura": fatura,
            "parcelas_visiveis": parcelas_visiveis,
            "subtotal_visivel": subtotal_visivel,
            "tem_itens_privados": subtotal_visivel != fatura.valor_total,
            "pode_pagar": pode_administrar,
            "pode_ajustar": pode_administrar and not fatura.esta_paga,
        },
    )


@login_required
def ajustar_fatura(request, fatura_id):
    fatura = _fatura_visivel(request, fatura_id)
    if not usuario_pode_administrar(fatura.cartao, request.user):
        raise Http404
    if fatura.esta_paga:
        messages.error(request, "Uma fatura paga não pode ter suas datas alteradas.")
        return redirect("cartoes:detalhe_fatura", fatura_id=fatura.pk)

    form = FaturaDatasForm(request.POST or None, instance=fatura)
    if request.method == "POST" and form.is_valid():
        try:
            atualizar_datas_fatura(
                fatura,
                form.cleaned_data["data_fechamento"],
                form.cleaned_data["data_vencimento"],
            )
        except CartaoErro as erro:
            form.add_error(None, str(erro))
        else:
            messages.success(
                request,
                "Datas desta fatura atualizadas. As compras permaneceram no mesmo ciclo.",
            )
            return redirect("cartoes:detalhe_fatura", fatura_id=fatura.pk)
    return render(
        request,
        "cartoes/ajustar_fatura.html",
        {
            "fatura": fatura,
            "form": form,
            "compras_afetadas": form.compras_afetadas,
        },
    )


@login_required
def pagar_fatura_view(request, fatura_id):
    sala = sala_ativa(request)
    fatura = _fatura_visivel(request, fatura_id)
    if not usuario_pode_administrar(fatura.cartao, request.user):
        messages.warning(
            request,
            "Somente o titular pode registrar o pagamento desta fatura individual.",
        )
        return redirect("cartoes:detalhe_fatura", fatura_id=fatura.pk)
    if fatura.esta_paga:
        messages.info(request, "Esta fatura já está paga.")
        return redirect("cartoes:detalhe_fatura", fatura_id=fatura.pk)

    form = PagamentoFaturaForm(
        request.POST or None,
        sala=sala,
        usuario=request.user,
        cartao=fatura.cartao,
    )
    if request.method == "POST" and form.is_valid():
        try:
            pagamento, foi_criado = pagar_fatura(
                fatura=fatura,
                conta=form.cleaned_data.get("conta"),
                data_pagamento=form.cleaned_data["data_pagamento"],
                usuario=request.user,
            )
        except CartaoErro as erro:
            messages.error(request, str(erro))
        else:
            if foi_criado:
                messages.success(request, "Pagamento da fatura registrado.")
                if pagamento.conta and pagamento.conta.saldo_atual < 0:
                    messages.warning(
                        request, f"O saldo de {pagamento.conta.nome} ficou negativo."
                    )
            else:
                messages.info(request, "Esta fatura já havia sido paga.")
        return redirect("cartoes:detalhe_fatura", fatura_id=fatura.pk)
    return render(request, "cartoes/pagar_fatura.html", {"fatura": fatura, "form": form})
