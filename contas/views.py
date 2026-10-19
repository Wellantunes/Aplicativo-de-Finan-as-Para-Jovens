from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from core.espacos import (
    recursos_disponiveis,
    sala_ativa,
    sala_do_usuario,
    usuario_pode_administrar,
)

from .forms import CartaoCreditoForm, ContaForm
from .models import CartaoCredito, Conta


def _conta_pode_deixar_de_ser_compartilhada(conta):
    sala = conta.sala_compartilhada
    if not sala:
        return True
    return not (
        conta.entradas.filter(Q(sala=sala) | Q(sala_compartilhada=sala)).exists()
        or conta.saidas.filter(Q(sala=sala) | Q(sala_compartilhada=sala)).exists()
        or conta.devolucoes_dizimo.filter(
            Q(entrada__sala=sala) | Q(entrada__sala_compartilhada=sala)
        ).exists()
        or conta.pagamentos_fatura.filter(
            Q(fatura__cartao__sala=sala)
            | Q(fatura__cartao__sala_compartilhada=sala)
        ).exists()
    )


def _cartao_pode_deixar_de_ser_compartilhado(cartao):
    sala = cartao.sala_compartilhada
    if not sala:
        return True
    return not cartao.compras.filter(
        Q(sala=sala) | Q(sala_compartilhada=sala)
    ).exists()


def _dados_de_propriedade(request, compartilhar=False):
    sala = sala_ativa(request)
    if sala:
        return {
            "sala": sala,
            "proprietario_usuario": None,
            "sala_compartilhada": None,
            "autor": request.user,
        }
    return {
        "sala": None,
        "proprietario_usuario": request.user,
        "sala_compartilhada": sala_do_usuario(request.user) if compartilhar else None,
        "autor": request.user,
    }


@login_required
def lista(request):
    sala = sala_ativa(request)
    contas = recursos_disponiveis(
        Conta.objects.select_related("titular", "proprietario_usuario"),
        request,
    )
    contexto = {
        "sala": sala,
        "titulo_espaco": sala.nome if sala else "Meu espaço",
        "contas_dinheiro": contas.filter(tipo=Conta.Tipo.DINHEIRO),
        "vales_alimentacao": contas.filter(tipo=Conta.Tipo.VALE_ALIMENTACAO),
    }
    return render(request, "contas/lista.html", contexto)


@login_required
def criar_conta(request):
    sala = sala_ativa(request)
    form = ContaForm(request.POST or None, sala=sala, usuario=request.user)

    if request.method == "POST" and form.is_valid():
        conta = form.save(commit=False)
        compartilhar = form.cleaned_data.get("compartilhar_sala", False)
        for campo, valor in _dados_de_propriedade(request, compartilhar).items():
            setattr(conta, campo, valor)
        conta.full_clean()
        conta.save()
        messages.success(request, "Conta cadastrada com sucesso.")
        return redirect("contas:lista")

    return render(
        request,
        "contas/formulario.html",
        {
            "form": form,
            "titulo": "Cadastrar conta",
            "descricao": "Registre uma conta em dinheiro ou um vale-alimentação.",
            "texto_botao": "Cadastrar conta",
        },
    )


@login_required
def editar_conta(request, conta_id):
    sala = sala_ativa(request)
    conta = get_object_or_404(recursos_disponiveis(Conta.objects.all(), request), pk=conta_id)
    if not usuario_pode_administrar(conta, request.user):
        raise Http404
    form = ContaForm(request.POST or None, instance=conta, sala=sala, usuario=request.user)

    if request.method == "POST" and form.is_valid():
        conta = form.save(commit=False)
        if conta.proprietario_usuario_id and "compartilhar_sala" in form.fields:
            compartilhar = form.cleaned_data.get("compartilhar_sala", False)
            if (
                not compartilhar
                and conta.sala_compartilhada_id
                and not _conta_pode_deixar_de_ser_compartilhada(conta)
            ):
                form.add_error(
                    "compartilhar_sala",
                    "Esta conta possui movimentos compartilhados. Remover o acesso deixaria o histórico financeiro inconsistente.",
                )
                return render(request, "contas/formulario.html", {
                    "form": form,
                    "titulo": "Editar conta",
                    "descricao": "Atualize os dados usados como ponto de partida.",
                    "texto_botao": "Salvar alterações",
                })
            conta.sala_compartilhada = (
                sala_do_usuario(request.user) if compartilhar else None
            )
        conta.full_clean()
        conta.save()
        messages.success(request, "Conta atualizada com sucesso.")
        return redirect("contas:lista")

    return render(
        request,
        "contas/formulario.html",
        {
            "form": form,
            "titulo": "Editar conta",
            "descricao": "Atualize os dados usados como ponto de partida.",
            "texto_botao": "Salvar alterações",
        },
    )


@login_required
def criar_cartao(request):
    sala = sala_ativa(request)
    form = CartaoCreditoForm(request.POST or None, sala=sala, usuario=request.user)

    if request.method == "POST" and form.is_valid():
        cartao = form.save(commit=False)
        cartao.titular = request.user
        compartilhar = form.cleaned_data.get("compartilhar_sala", False)
        for campo, valor in _dados_de_propriedade(request, compartilhar).items():
            setattr(cartao, campo, valor)
        cartao.full_clean()
        cartao.save()
        messages.success(request, "Cartão cadastrado com sucesso.")
        return redirect("cartoes:lista")

    return render(
        request,
        "contas/formulario.html",
        {
            "form": form,
            "titulo": "Cadastrar cartão",
            "descricao": "Defina a cor e as regras usadas nos próximos ciclos.",
            "texto_botao": "Cadastrar cartão",
            "tipo_formulario": "cartao",
            "url_cancelar": "cartoes:lista",
        },
    )


@login_required
def editar_cartao(request, cartao_id):
    sala = sala_ativa(request)
    cartao = get_object_or_404(
        recursos_disponiveis(CartaoCredito.objects.all(), request),
        pk=cartao_id,
    )
    if not usuario_pode_administrar(cartao, request.user):
        raise Http404
    form = CartaoCreditoForm(
        request.POST or None,
        instance=cartao,
        sala=sala,
        usuario=request.user,
    )

    if request.method == "POST" and form.is_valid():
        cartao = form.save(commit=False)
        if cartao.proprietario_usuario_id and "compartilhar_sala" in form.fields:
            compartilhar = form.cleaned_data.get("compartilhar_sala", False)
            if (
                not compartilhar
                and cartao.sala_compartilhada_id
                and not _cartao_pode_deixar_de_ser_compartilhado(cartao)
            ):
                form.add_error(
                    "compartilhar_sala",
                    "Este cartão possui compras compartilhadas. Remover o acesso deixaria parcelas ou faturas inconsistentes.",
                )
                return render(request, "contas/formulario.html", {
                    "form": form,
                    "titulo": "Editar cartão",
                    "descricao": "Atualize o titular ou os dias do cartão.",
                    "texto_botao": "Salvar alterações",
                })
            cartao.sala_compartilhada = (
                sala_do_usuario(request.user) if compartilhar else None
            )
        cartao.full_clean()
        cartao.save()
        messages.success(request, "Cartão atualizado com sucesso.")
        return redirect("cartoes:detalhe_cartao", cartao_id=cartao.pk)

    return render(
        request,
        "contas/formulario.html",
        {
            "form": form,
            "titulo": "Editar cartão",
            "descricao": "Atualize o titular ou os dias do cartão.",
            "texto_botao": "Salvar alterações",
            "tipo_formulario": "cartao",
            "url_cancelar": "cartoes:detalhe_cartao",
            "cartao": cartao,
        },
    )
