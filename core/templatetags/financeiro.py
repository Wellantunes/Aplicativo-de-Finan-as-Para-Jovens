from decimal import Decimal, InvalidOperation

from django import template


register = template.Library()


@register.filter
def moeda_br(valor):
    """Formata um Decimal como moeda brasileira, inclusive valores negativos."""

    try:
        numero = Decimal(valor or 0).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        numero = Decimal("0.00")
    negativo = numero < 0
    numero = abs(numero)
    formatado = f"{numero:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{'-' if negativo else ''}R$ {formatado}"
