from django.db import transaction

from django.contrib.auth import get_user_model

from salas.models import Sala

from .models import Saida


@transaction.atomic
def criar_saida(
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
    existente = Saida.objects.filter(chave_idempotencia=chave_idempotencia).first()
    if existente:
        return existente, False

    saida = Saida(
        sala=sala,
        proprietario_usuario=proprietario_usuario,
        sala_compartilhada=sala_compartilhada,
        autor=autor,
        chave_idempotencia=chave_idempotencia,
        **dados,
    )
    saida.full_clean()
    saida.save()
    return saida, True


@transaction.atomic
def atualizar_saida(saida, dados):
    saida_bloqueada = Saida.objects.select_for_update().get(pk=saida.pk)
    for campo, valor in dados.items():
        setattr(saida_bloqueada, campo, valor)
    saida_bloqueada.full_clean()
    saida_bloqueada.save()
    return saida_bloqueada


@transaction.atomic
def excluir_saida(saida):
    saida_bloqueada = Saida.objects.select_for_update().get(pk=saida.pk)
    saida_bloqueada.delete()


@transaction.atomic
def marcar_saida_como_paga(saida, data_pagamento, forma_pagamento="", conta=None):
    saida_bloqueada = Saida.objects.select_for_update().get(pk=saida.pk)
    if saida_bloqueada.situacao == Saida.Situacao.PAGA:
        return saida_bloqueada, False
    if saida_bloqueada.situacao == Saida.Situacao.CANCELADA:
        return saida_bloqueada, False

    saida_bloqueada.situacao = Saida.Situacao.PAGA
    saida_bloqueada.data_pagamento = data_pagamento
    saida_bloqueada.forma_pagamento = forma_pagamento
    saida_bloqueada.conta = conta
    saida_bloqueada.full_clean()
    saida_bloqueada.save()
    return saida_bloqueada, True
