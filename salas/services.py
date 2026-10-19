from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import ConviteSala, MembroSala, Sala, gerar_codigo_convite


LIMITE_MEMBROS = 2


class SalaErro(Exception):
    """Erro esperado ao criar uma sala ou aceitar um convite."""


def _criar_novo_convite(sala, criado_por):
    for _ in range(5):
        codigo = gerar_codigo_convite()
        if not ConviteSala.objects.filter(codigo=codigo).exists():
            return ConviteSala.objects.create(
                sala=sala,
                codigo=codigo,
                criado_por=criado_por,
            )

    raise SalaErro("Não foi possível gerar um código. Tente novamente.")


@transaction.atomic
def criar_sala_com_convite(
    usuario,
    nome,
    orcamento_mensal,
    tipo=Sala.Tipo.CASAL,
    simbolo=Sala.Simbolo.CORACAO,
    controlar_dizimos=False,
):
    usuario_bloqueado = get_user_model().objects.select_for_update().get(pk=usuario.pk)

    if MembroSala.objects.filter(usuario=usuario_bloqueado).exists():
        raise SalaErro("Você já participa de uma sala.")

    sala = Sala.objects.create(
        nome=nome,
        tipo=tipo,
        simbolo=simbolo,
        orcamento_mensal=orcamento_mensal,
        controlar_dizimos=controlar_dizimos,
        criado_por=usuario_bloqueado,
    )
    MembroSala.objects.create(sala=sala, usuario=usuario_bloqueado)
    convite = _criar_novo_convite(sala, usuario_bloqueado)
    return sala, convite


@transaction.atomic
def obter_ou_criar_convite(sala, usuario):
    sala_bloqueada = Sala.objects.select_for_update().get(pk=sala.pk)

    if not MembroSala.objects.filter(
        sala=sala_bloqueada,
        usuario=usuario,
    ).exists():
        raise SalaErro("Você não tem acesso a esta sala.")

    if sala_bloqueada.membros.count() >= LIMITE_MEMBROS:
        raise SalaErro("Esta sala já possui dois participantes.")

    convite_ativo = sala_bloqueada.convites.filter(
        usado_em__isnull=True,
        expira_em__gt=timezone.now(),
    ).first()
    if convite_ativo:
        return convite_ativo

    return _criar_novo_convite(sala_bloqueada, usuario)


@transaction.atomic
def aceitar_convite(usuario, codigo):
    usuario_bloqueado = get_user_model().objects.select_for_update().get(pk=usuario.pk)

    if MembroSala.objects.filter(usuario=usuario_bloqueado).exists():
        raise SalaErro("Você já participa de uma sala.")

    convite_inicial = ConviteSala.objects.filter(codigo=codigo).only("sala_id").first()
    if not convite_inicial:
        raise SalaErro("Código de convite inválido.")

    sala = Sala.objects.select_for_update().get(pk=convite_inicial.sala_id)
    convite = ConviteSala.objects.select_for_update().get(pk=convite_inicial.pk)

    if convite.usado_em is not None:
        raise SalaErro("Este convite já foi utilizado.")

    if convite.expira_em <= timezone.now():
        raise SalaErro("Este convite expirou.")

    if sala.membros.count() >= LIMITE_MEMBROS:
        raise SalaErro("Esta sala já possui dois participantes.")

    MembroSala.objects.create(sala=sala, usuario=usuario_bloqueado)
    convite.usado_em = timezone.now()
    convite.usado_por = usuario_bloqueado
    convite.save(update_fields=["usado_em", "usado_por"])
    return sala
