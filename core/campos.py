import re
from decimal import Decimal, InvalidOperation

from django import forms


class ValorBrasileiroField(forms.DecimalField):
    """Campo decimal que aceita valores comuns escritos no Brasil."""

    def __init__(self, *args, **kwargs):
        atributos = {
            "inputmode": "decimal",
            "autocomplete": "off",
            "data-money-input": "",
            "placeholder": "R$ 0,00",
        }
        widget = kwargs.pop("widget", None)
        if widget:
            atributos.update(widget.attrs)
        kwargs["widget"] = forms.TextInput(attrs=atributos)
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if isinstance(value, str):
            value = self._normalizar_valor(value)
        try:
            return super().to_python(value)
        except (InvalidOperation, ValueError):
            raise forms.ValidationError("Informe um valor válido.")

    @staticmethod
    def _normalizar_valor(value):
        texto = re.sub(r"\s+", "", value.strip())
        if texto.upper().startswith("R$"):
            texto = texto[2:]
        if not texto:
            return texto

        correspondencia = re.fullmatch(r"([+-]?)([0-9.,]+)", texto)
        if not correspondencia:
            raise forms.ValidationError(
                "Informe um valor usando apenas números, ponto ou vírgula."
            )
        sinal, numero = correspondencia.groups()

        if "," in numero and "." in numero:
            if numero.count(",") != 1 or numero.rfind(",") < numero.rfind("."):
                raise forms.ValidationError("Use o formato brasileiro, como 1.234,56.")
            inteiro, centavos = numero.split(",")
            if not centavos:
                raise forms.ValidationError("Informe os centavos depois da vírgula.")
            if not ValorBrasileiroField._agrupamento_valido(inteiro):
                raise forms.ValidationError("Use pontos somente para separar milhares.")
            inteiro = inteiro.replace(".", "")
        elif "," in numero:
            if numero.count(",") != 1:
                raise forms.ValidationError("Use somente uma vírgula para os centavos.")
            inteiro, centavos = numero.split(",")
            if not centavos:
                raise forms.ValidationError("Informe os centavos depois da vírgula.")
            if len(centavos) == 3:
                raise forms.ValidationError(
                    "Use no máximo dois dígitos após a vírgula."
                )
        elif "." in numero:
            partes = numero.split(".")
            if len(partes) > 2:
                if not ValorBrasileiroField._agrupamento_valido(numero):
                    raise forms.ValidationError("Use pontos somente para separar milhares.")
                inteiro, centavos = numero.replace(".", ""), ""
            else:
                inteiro, ultima_parte = partes
                if not ultima_parte:
                    raise forms.ValidationError("Informe os centavos depois do ponto.")
                if len(ultima_parte) == 3:
                    if not ValorBrasileiroField._agrupamento_valido(numero):
                        raise forms.ValidationError(
                            "Use no máximo dois dígitos para os centavos."
                        )
                    inteiro, centavos = numero.replace(".", ""), ""
                else:
                    centavos = ultima_parte
        else:
            inteiro, centavos = numero, ""

        if not inteiro:
            inteiro = "0"
        if not inteiro.isdigit() or (centavos and not centavos.isdigit()):
            raise forms.ValidationError("Informe um valor válido.")
        if len(centavos) > 2:
            raise forms.ValidationError("Use no máximo dois dígitos para os centavos.")
        return Decimal(f"{sinal}{inteiro}.{centavos or '0'}")

    @staticmethod
    def _agrupamento_valido(numero):
        partes = numero.split(".")
        return (
            len(partes) > 1
            and 1 <= len(partes[0]) <= 3
            and partes[0].isdigit()
            and all(len(parte) == 3 and parte.isdigit() for parte in partes[1:])
        )
