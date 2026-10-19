from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone

from cartoes.models import CompraCredito
from contas.models import CartaoCredito, Conta
from entradas.models import ConfiguracaoDizimo, Entrada, FormaCalculoDizimo, TipoEntrada
from saidas.models import Saida
from core.espacos import sala_do_usuario

from .forms import (
    ConfiguracaoDizimoInicialForm,
    ConfiguracaoInicialFinalForm,
    ConfiguracaoRendaForm,
    AvatarForm,
    CompartilhamentoForm,
    PerfilFinanceiroForm,
)
from .avatar_catalogo import (
    BARBAS,
    BASES,
    CABELOS,
    CORES_CABELO,
    CORES_ROUPA,
    ROUPAS,
    TONS_PELE,
)


TIPOS_DINHEIRO = [
    TipoEntrada.SALARIO,
    TipoEntrada.EXTRA,
    TipoEntrada.SEGUNDO_EMPREGO,
    TipoEntrada.FGTS,
    TipoEntrada.DECIMO_TERCEIRO,
    TipoEntrada.OUTROS,
]


def _destino_depois_do_avatar(request):
    destino = request.POST.get("next") or request.GET.get("next")
    if destino and url_has_allowed_host_and_scheme(
        destino,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return destino
    if not request.user.configuracao_inicial_concluida:
        return reverse("usuarios:configuracao_renda")
    return reverse("dashboard:mensal")


@login_required
def editar_avatar(request):
    campos_avatar_v2 = (
        "avatar_v2_base",
        "avatar_v2_pele",
        "avatar_v2_cabelo",
        "avatar_v2_cor_cabelo",
        "avatar_v2_barba",
        "avatar_v2_roupa",
        "avatar_v2_cor_roupa",
    )
    avatar_salvo = {
        campo: getattr(request.user, campo)
        for campo in campos_avatar_v2
    }
    avatar_salvo["existe"] = request.user.usa_avatar_v2
    form = AvatarForm(request.POST or None, instance=request.user)
    destino = _destino_depois_do_avatar(request)
    if request.method == "POST":
        if form.is_valid():
            usuario = form.save(commit=False)
            usuario.avatar_concluido = True
            usuario.save()
            messages.success(request, "Avatar salvo com sucesso.")
            return redirect(destino)
        for campo in campos_avatar_v2:
            setattr(request.user, campo, avatar_salvo[campo])
    return render(
        request,
        "usuarios/avatar.html",
        {
            "form": form,
            "avatar_salvo": avatar_salvo,
            "destino": destino,
            "cancelar_url": (
                destino
                if request.user.avatar_concluido
                else reverse("account_logout")
            ),
            "bases_avatar": BASES,
            "tons_pele_avatar": TONS_PELE,
            "cabelos_avatar": CABELOS,
            "cores_cabelo_avatar": CORES_CABELO,
            "barbas_avatar": BARBAS,
            "roupas_avatar": ROUPAS,
            "cores_roupa_avatar": CORES_ROUPA,
        },
    )


def _sincronizar_configuracoes_dizimo(usuario):
    tipos = [*TIPOS_DINHEIRO, TipoEntrada.VALE_ALIMENTACAO]
    for tipo in tipos:
        incluir_tipo = tipo != TipoEntrada.VALE_ALIMENTACAO or usuario.incluir_vale_no_dizimo
        calcular = (
            usuario.dizimo_automatico
            and incluir_tipo
            and usuario.percentual_dizimo_padrao > 0
        )
        ConfiguracaoDizimo.objects.update_or_create(
            proprietario_usuario=usuario,
            tipo_entrada=tipo,
            defaults={
                "sala": None,
                "pessoa": usuario,
                "calcular_dizimo": calcular,
                "forma_calculo": (
                    FormaCalculoDizimo.PERCENTUAL if calcular else ""
                ),
                "percentual_dizimo": (
                    usuario.percentual_dizimo_padrao if calcular else None
                ),
                "valor_dizimo_manual": None,
            },
        )


@login_required
def configuracao_renda(request):
    form = ConfiguracaoRendaForm(request.POST or None, instance=request.user)
    if request.method == "POST":
        if "pular" in request.POST or form.is_valid():
            if "pular" not in request.POST:
                form.save()
            return redirect("usuarios:configuracao_dizimo")
    return render(
        request,
        "usuarios/configuracao_renda.html",
        {"form": form, "etapa": 1},
    )


@login_required
def configuracao_dizimo(request):
    form = ConfiguracaoDizimoInicialForm(request.POST or None, instance=request.user)
    if request.method == "POST":
        if "pular" in request.POST:
            return redirect("usuarios:configuracao_final")
        if form.is_valid():
            usuario = form.save()
            _sincronizar_configuracoes_dizimo(usuario)
            return redirect("usuarios:configuracao_final")
    return render(
        request,
        "usuarios/configuracao_dizimo.html",
        {"form": form, "etapa": 2},
    )


@login_required
def configuracao_final(request):
    form = ConfiguracaoInicialFinalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        request.user.configuracao_inicial_concluida = True
        request.user.save(update_fields=["configuracao_inicial_concluida"])
        destino = form.cleaned_data["proximo_passo"]
        if destino == "conta":
            return redirect("contas:criar_conta")
        if destino == "cartao":
            return redirect("contas:criar_cartao")
        return redirect("dashboard:mensal")
    return render(
        request,
        "usuarios/configuracao_final.html",
        {"form": form, "etapa": 3},
    )


@login_required
def perfil(request):
    form = PerfilFinanceiroForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        usuario = form.save(commit=False)
        usuario.configuracao_inicial_concluida = True
        usuario.save()
        _sincronizar_configuracoes_dizimo(usuario)
        messages.success(request, "Preferências do perfil atualizadas.")
        return redirect("usuarios:perfil")
    possui_contas_legadas = Conta.objects.filter(
        proprietario_usuario=request.user
    ).exists()
    return render(
        request,
        "usuarios/perfil.html",
        {
            "form": form,
            "possui_contas_legadas": possui_contas_legadas,
        },
    )


def _lancamentos_para_compartilhar(usuario, alcance, contas, cartoes):
    entradas = Entrada.objects.filter(proprietario_usuario=usuario).exclude(
        situacao=Entrada.Situacao.CANCELADA
    ).filter(
        Q(conta_destino__isnull=True) | Q(conta_destino__in=contas)
    )
    saidas = Saida.objects.filter(proprietario_usuario=usuario).exclude(
        situacao=Saida.Situacao.CANCELADA
    ).filter(
        Q(conta__isnull=True) | Q(conta__in=contas)
    )
    compras = CompraCredito.objects.filter(
        proprietario_usuario=usuario,
        cartao__in=cartoes,
    )

    if alcance == "nenhum":
        return entradas.none(), saidas.none(), compras.none()
    if alcance == "mes_atual":
        inicio = timezone.localdate().replace(day=1)
        entradas = entradas.filter(
            Q(data_prevista__gte=inicio)
            | Q(data_prevista__isnull=True, data__gte=inicio)
        )
        saidas = saidas.filter(
            Q(vencimento__gte=inicio)
            | Q(vencimento__isnull=True, data_pagamento__gte=inicio)
        )
        compras = compras.filter(data_compra__gte=inicio)
    return entradas, saidas, compras


def _conta_tem_movimento_da_sala(conta, sala):
    return (
        conta.entradas.filter(sala=sala).exists()
        or conta.devolucoes_dizimo.filter(entrada__sala=sala).exists()
        or conta.saidas.filter(sala=sala).exists()
        or conta.pagamentos_fatura.filter(fatura__cartao__sala=sala).exists()
    )


def _cartao_tem_compra_da_sala(cartao, sala):
    return cartao.compras.filter(sala=sala).exists()


def _atualizar_compartilhamento(
    *, usuario, sala, contas, cartoes, entradas, saidas, compras
):
    """Reconcilia o consentimento sem copiar ou trocar a propriedade dos dados."""

    Entrada.objects.filter(
        proprietario_usuario=usuario,
        sala_compartilhada=sala,
    ).update(sala_compartilhada=None)
    Saida.objects.filter(
        proprietario_usuario=usuario,
        sala_compartilhada=sala,
    ).update(sala_compartilhada=None)
    CompraCredito.objects.filter(
        proprietario_usuario=usuario,
        sala_compartilhada=sala,
    ).update(sala_compartilhada=None)

    contas_selecionadas = set(contas.values_list("pk", flat=True))
    contas_para_retirar = Conta.objects.filter(
        proprietario_usuario=usuario,
        sala_compartilhada=sala,
    ).exclude(pk__in=contas_selecionadas)
    for conta in contas_para_retirar:
        if not _conta_tem_movimento_da_sala(conta, sala):
            conta.sala_compartilhada = None
            conta.save(update_fields=["sala_compartilhada"])

    cartoes_selecionados = set(cartoes.values_list("pk", flat=True))
    cartoes_para_retirar = CartaoCredito.objects.filter(
        proprietario_usuario=usuario,
        sala_compartilhada=sala,
    ).exclude(pk__in=cartoes_selecionados)
    for cartao in cartoes_para_retirar:
        if not _cartao_tem_compra_da_sala(cartao, sala):
            cartao.sala_compartilhada = None
            cartao.save(update_fields=["sala_compartilhada"])

    contas.update(sala_compartilhada=sala)
    cartoes.update(sala_compartilhada=sala)
    entradas.update(sala_compartilhada=sala)
    saidas.update(sala_compartilhada=sala)
    compras.update(sala_compartilhada=sala)


@login_required
def compartilhamento(request):
    sala = sala_do_usuario(request.user)
    if not sala:
        messages.info(request, "Crie ou entre em uma sala antes de compartilhar dados.")
        return redirect("salas:minha_sala")

    form = CompartilhamentoForm(request.POST or None, usuario=request.user)
    previa = None
    if request.method == "POST" and form.is_valid():
        contas = form.cleaned_data["contas"]
        cartoes = form.cleaned_data["cartoes"]
        entradas, saidas, compras = _lancamentos_para_compartilhar(
            request.user,
            form.cleaned_data["alcance"],
            contas,
            cartoes,
        )
        previa = {
            "contas": contas.count(),
            "cartoes": cartoes.count(),
            "entradas": entradas.count(),
            "saidas": saidas.count(),
            "compras": compras.count(),
        }
        if request.POST.get("acao") == "confirmar":
            with transaction.atomic():
                _atualizar_compartilhamento(
                    usuario=request.user,
                    sala=sala,
                    contas=contas,
                    cartoes=cartoes,
                    entradas=entradas,
                    saidas=saidas,
                    compras=compras,
                )
                request.user.compartilhar_novos_lancamentos = form.cleaned_data[
                    "compartilhar_novos"
                ]
                request.user.save(update_fields=["compartilhar_novos_lancamentos"])
            messages.success(request, "Compartilhamento atualizado com seu consentimento.")
            return redirect("usuarios:compartilhamento")

    return render(request, "usuarios/compartilhamento.html", {
        "form": form,
        "sala": sala,
        "previa": previa,
    })
