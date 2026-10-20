from decimal import InvalidOperation

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
            texto = value.strip().replace("R$", "").replace(" ", "")
            if "," in texto:
                texto = texto.replace(".", "").replace(",", ".")
            value = texto
        try:
            return super().to_python(value)
        except (InvalidOperation, ValueError):
            raise forms.ValidationError("Informe um valor válido.")
