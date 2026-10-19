from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.espacos import definir_espaco_individual, definir_espaco_sala

from .forms import CodigoConviteForm, SalaForm
from .models import ConviteSala, MembroSala, Sala
from .services import SalaErro, aceitar_convite, criar_sala_com_convite, obter_ou_criar_convite


def _sala_do_usuario(usuario):
    vinculo = MembroSala.objects.select_related("sala").filter(usuario=usuario).first()
    return vinculo.sala if vinculo else None


def _convite_disponivel(codigo):
    convite = ConviteSala.objects.select_related("sala").filter(codigo=codigo).first()

    if not convite:
        raise SalaErro("Código de convite inválido.")
    if convite.usado_em is not None:
        raise SalaErro("Este convite já foi utilizado.")
    if convite.expira_em <= timezone.now():
        raise SalaErro("Este convite expirou.")
    if convite.sala.membros.count() >= 2:
        raise SalaErro("Esta sala já possui dois participantes.")

    return convite


@login_required
def criar_sala(request):
    sala_existente = _sala_do_usuario(request.user)
    if sala_existente:
        messages.warning(request, "Você já participa de uma sala.")
        return redirect("salas:detalhe", sala_id=sala_existente.pk)

    form = SalaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            sala, _ = criar_sala_com_convite(
                usuario=request.user,
                nome=form.cleaned_data["nome"],
                tipo=form.cleaned_data["tipo"],
                simbolo=form.cleaned_data["simbolo"],
                orcamento_mensal=form.cleaned_data["orcamento_mensal"],
                controlar_dizimos=form.cleaned_data["controlar_dizimos"],
            )
        except SalaErro as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Sala criada. Compartilhe o código com a outra pessoa.")
            return redirect("salas:detalhe", sala_id=sala.pk)

    return render(request, "salas/criar.html", {"form": form})


@login_required
def configurar_sala(request, sala_id):
    sala = get_object_or_404(Sala, pk=sala_id, membros__usuario=request.user)
    form = SalaForm(request.POST or None, instance=sala)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Configurações da sala atualizadas.")
        return redirect("salas:detalhe", sala_id=sala.pk)

    return render(request, "salas/configurar.html", {"form": form, "sala": sala})


@login_required
def informar_codigo(request):
    sala_existente = _sala_do_usuario(request.user)
    if sala_existente:
        messages.warning(request, "Você já participa de uma sala.")
        return redirect("salas:detalhe", sala_id=sala_existente.pk)

    form = CodigoConviteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        return redirect(
            "salas:confirmar_entrada",
            codigo=form.cleaned_data["codigo"],
        )

    return render(request, "salas/entrar.html", {"form": form})


@login_required
def confirmar_entrada(request, codigo):
    sala_existente = _sala_do_usuario(request.user)
    if sala_existente:
        messages.warning(request, "Você já participa de uma sala.")
        return redirect("salas:detalhe", sala_id=sala_existente.pk)

    codigo = codigo.upper()
    try:
        convite = _convite_disponivel(codigo)
    except SalaErro as erro:
        messages.error(request, str(erro))
        return redirect("salas:entrar")

    if request.method == "POST":
        try:
            sala = aceitar_convite(request.user, codigo)
        except SalaErro as erro:
            messages.error(request, str(erro))
            return redirect("salas:entrar")

        messages.success(request, f"Você entrou na sala {sala.nome}.")
        return redirect("salas:detalhe", sala_id=sala.pk)

    return render(request, "salas/confirmar_entrada.html", {"convite": convite})


@login_required
def detalhe_sala(request, sala_id):
    sala = get_object_or_404(
        Sala.objects.prefetch_related("membros__usuario", "convites"),
        pk=sala_id,
        membros__usuario=request.user,
    )
    convite_ativo = None
    if sala.membros.count() < 2:
        convite_ativo = sala.convites.filter(
            usado_em__isnull=True,
            expira_em__gt=timezone.now(),
        ).first()

    return render(
        request,
        "salas/detalhe.html",
        {"sala": sala, "convite_ativo": convite_ativo},
    )


@login_required
def minha_sala(request):
    sala = _sala_do_usuario(request.user)
    if sala:
        sala = Sala.objects.prefetch_related("membros__usuario").get(pk=sala.pk)
    return render(request, "salas/lista.html", {"sala": sala})


@login_required
def entrar_espaco(request, sala_id):
    sala = get_object_or_404(Sala, pk=sala_id, membros__usuario=request.user)
    if request.method != "POST":
        return redirect("salas:minha_sala")
    definir_espaco_sala(request, sala)
    messages.success(request, f"Você entrou no espaço compartilhado {sala.nome}.")
    return redirect("dashboard:mensal")


@login_required
def voltar_individual(request):
    definir_espaco_individual(request)
    messages.info(request, "Você voltou ao seu espaço individual.")
    return redirect("dashboard:mensal")


@login_required
def gerar_convite(request, sala_id):
    if request.method != "POST":
        return redirect("salas:detalhe", sala_id=sala_id)

    sala = get_object_or_404(Sala, pk=sala_id, membros__usuario=request.user)
    try:
        obter_ou_criar_convite(sala, request.user)
    except SalaErro as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, "Código de convite disponível por 24 horas.")

    return redirect("salas:detalhe", sala_id=sala.pk)
