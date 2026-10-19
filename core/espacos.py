from django.db.models import Q

from salas.models import MembroSala


ESPACO_INDIVIDUAL = "individual"
ESPACO_SALA = "sala"
CHAVE_ESPACO_SESSAO = "espaco_financeiro"


def sala_do_usuario(usuario):
    vinculo = MembroSala.objects.select_related("sala").filter(usuario=usuario).first()
    return vinculo.sala if vinculo else None


def sala_para_novo_compartilhamento(usuario):
    """Retorna a sala atual somente quando o compartilhamento automatico esta ativo."""

    if not usuario.compartilhar_novos_lancamentos:
        return None
    return sala_do_usuario(usuario)


def definir_espaco_individual(request):
    request.session[CHAVE_ESPACO_SESSAO] = ESPACO_INDIVIDUAL


def definir_espaco_sala(request, sala):
    if not sala.membros.filter(usuario=request.user).exists():
        raise PermissionError("O usuário não participa desta sala.")
    request.session[CHAVE_ESPACO_SESSAO] = ESPACO_SALA


def sala_ativa(request):
    sessao = getattr(request, "session", {})
    espaco = sessao.get(CHAVE_ESPACO_SESSAO)
    if espaco == ESPACO_SALA:
        return sala_do_usuario(request.user)
    return None


def filtro_do_espaco(request):
    sala = sala_ativa(request)
    if sala:
        return Q(sala=sala) | Q(
            proprietario_usuario__isnull=False,
            sala_compartilhada=sala,
            proprietario_usuario__vinculo_sala__sala=sala,
        )
    return Q(proprietario_usuario=request.user)


def filtrar_no_espaco(queryset, request):
    return queryset.filter(filtro_do_espaco(request))


def recursos_disponiveis(queryset, request):
    """Contas e cartões utilizáveis no espaço atual, sem duplicar registros."""

    return filtrar_no_espaco(queryset, request).distinct()


def usuario_pode_administrar(registro, usuario):
    if registro.proprietario_usuario_id:
        return registro.proprietario_usuario_id == usuario.pk
    return bool(
        registro.sala_id
        and registro.sala.membros.filter(usuario=usuario).exists()
    )


def contexto_espaco(request):
    if not request.user.is_authenticated:
        return {
            "espaco_atual": ESPACO_INDIVIDUAL,
            "sala_ativa": None,
            "sala_usuario": None,
        }

    sala_usuario = sala_do_usuario(request.user)
    sala_selecionada = sala_ativa(request)
    return {
        "espaco_atual": ESPACO_SALA if sala_selecionada else ESPACO_INDIVIDUAL,
        "sala_ativa": sala_selecionada,
        "sala_usuario": sala_usuario,
    }
