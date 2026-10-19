import re
from calendar import monthrange
from datetime import date

from django.db.models import Q
from django.utils import timezone


PADRAO_MES = re.compile(r"\d{4}-(0[1-9]|1[0-2])")


def mes_de_referencia(valor=None):
    """Retorna o mês informado ou o mês atual quando o valor não é válido."""

    if valor and PADRAO_MES.fullmatch(valor):
        ano, mes = (int(parte) for parte in valor.split("-"))
    else:
        hoje = timezone.localdate()
        ano, mes = hoje.year, hoje.month
    return f"{ano:04d}-{mes:02d}", ano, mes


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
