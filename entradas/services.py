from django.db import transaction

from django.contrib.auth import get_user_model

from salas.models import Sala

from .models import DevolucaoDizimo, Entrada


class EntradaErro(Exception):
    """Erro esperado ao alterar uma entrada ou devolução."""


@transaction.atomic
def criar_entrada(
    sala,
    chave_idempotencia,
    dados,
    proprietario_usuario=None,
    autor=None,
    sala_compartilhada=None,
):
    if sala:
        Sala.objects.select_for_update().get(pk=sala.pk)
    elif proprietario_usuario:
        get_user_model().objects.select_for_update().get(pk=proprietario_usuario.pk)
    existente = Entrada.objects.filter(chave_idempotencia=chave_idempotencia).first()
    if existente:
        return existente, False

    entrada = Entrada(
        sala=sala,
        proprietario_usuario=proprietario_usuario,
        sala_compartilhada=sala_compartilhada,
        autor=autor,
        chave_idempotencia=chave_idempotencia,
        **dados,
    )
    entrada.full_clean()
    entrada.save()
    return entrada, True


@transaction.atomic
def atualizar_entrada(entrada, dados):
    entrada_bloqueada = Entrada.objects.select_for_update().get(pk=entrada.pk)
    if entrada_bloqueada.devolucoes.exists():
        raise EntradaErro(
            "Esta entrada possui devoluções vinculadas e não pode ser editada nesta versão."
        )

    for campo, valor in dados.items():
        setattr(entrada_bloqueada, campo, valor)
    entrada_bloqueada.full_clean()
    entrada_bloqueada.save()
    return entrada_bloqueada


@transaction.atomic
def excluir_entrada(entrada):
    entrada_bloqueada = Entrada.objects.select_for_update().get(pk=entrada.pk)
    if entrada_bloqueada.devolucoes.exists():
        raise EntradaErro(
            "Esta entrada possui devoluções vinculadas e não pode ser excluída nesta versão."
        )
    entrada_bloqueada.delete()


@transaction.atomic
def marcar_entrada_como_recebida(entrada, data_recebimento):
    entrada_bloqueada = Entrada.objects.select_for_update().get(pk=entrada.pk)
    if entrada_bloqueada.situacao == Entrada.Situacao.RECEBIDA:
        return entrada_bloqueada, False
    if entrada_bloqueada.situacao == Entrada.Situacao.CANCELADA:
        raise EntradaErro("Uma entrada cancelada precisa ser editada antes da confirmação.")

    entrada_bloqueada.situacao = Entrada.Situacao.RECEBIDA
    entrada_bloqueada.data = data_recebimento
    entrada_bloqueada.full_clean()
    entrada_bloqueada.save()
    return entrada_bloqueada, True


@transaction.atomic
def registrar_devolucao(entrada, usuario, chave_idempotencia, dados):
    entrada_bloqueada = Entrada.objects.select_for_update().get(pk=entrada.pk)
    if entrada_bloqueada.situacao != Entrada.Situacao.RECEBIDA:
        raise EntradaErro("Confirme o recebimento antes de registrar a devolução.")
    existente = DevolucaoDizimo.objects.filter(
        chave_idempotencia=chave_idempotencia
    ).first()
    if existente:
        return existente, False

    valor = dados["valor"]
    if valor > entrada_bloqueada.dizimo_restante:
        raise EntradaErro("O valor supera o dízimo restante desta entrada.")

    devolucao = DevolucaoDizimo(
        entrada=entrada_bloqueada,
        registrado_por=usuario,
        chave_idempotencia=chave_idempotencia,
        **dados,
    )
    devolucao.full_clean()
    devolucao.save()
    return devolucao, True
