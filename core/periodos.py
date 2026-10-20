import re
from calendar import monthrange
from datetime import date

from django.db.models import Q
from django.utils import timezone


PADRAO_MES = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
CHAVE_MES_SESSAO = "mes_financeiro_ativo"


def mes_de_referencia(valor=None):
    """Retorna o mês informado ou o mês atual quando o valor não é válido."""

    if valor and PADRAO_MES.fullmatch(valor):
        ano, mes = (int(parte) for parte in valor.split("-"))
    else:
        hoje = timezone.localdate()
        ano, mes = hoje.year, hoje.month
    return f"{ano:04d}-{mes:02d}", ano, mes


def mes_ativo(request, valor=None):
    """Mantém o mês escolhido somente durante a sessão autenticada atual."""

    if valor and PADRAO_MES.fullmatch(valor):
        request.session[CHAVE_MES_SESSAO] = valor
    elif not request.session.get(CHAVE_MES_SESSAO):
        request.session[CHAVE_MES_SESSAO] = timezone.localdate().strftime("%Y-%m")
    return mes_de_referencia(request.session[CHAVE_MES_SESSAO])


def data_inicial_do_mes(ano, mes):
    """Usa o dia de hoje no mês ativo ou o último dia válido daquele mês."""

    dia = min(timezone.localdate().day, monthrange(ano, mes)[1])
    return date(ano, mes, dia)


def contexto_periodo(request):
    if not request.user.is_authenticated:
        return {}
    mes, _, _ = mes_ativo(request, request.GET.get("mes"))
    return {"mes_navegacao": mes}


def limites_do_mes(ano, mes):
    return date(ano, mes, 1), date(ano, mes, monthrange(ano, mes)[1])


def filtrar_entradas_por_referencia(queryset, inicio, fim):
    """Usa a data prevista; `data` é fallback para registros históricos."""

    return queryset.filter(
        Q(data_prevista__range=(inicio, fim))
        | Q(data_prevista__isnull=True, data__range=(inicio, fim))
    )


def filtrar_saidas_por_referencia(queryset, inicio, fim):
    """Usa o vencimento; a data paga é fallback para registros históricos."""

    return queryset.filter(
        Q(vencimento__range=(inicio, fim))
        | Q(vencimento__isnull=True, data_pagamento__range=(inicio, fim))
    )
