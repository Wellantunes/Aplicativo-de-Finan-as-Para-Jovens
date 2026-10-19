from django import forms

from .models import Sala, TAMANHO_CODIGO_CONVITE


class SalaForm(forms.ModelForm):
    tipo = forms.ChoiceField(
        label="Tipo",
        required=False,
        choices=Sala.Tipo.choices,
        widget=forms.Select(attrs={"data-room-type": ""}),
    )
    simbolo = forms.ChoiceField(
        label="Símbolo decorativo",
        required=False,
        choices=[
            ("", "Usar o padrão do tipo"),
            *Sala.Simbolo.choices,
        ],
    )

    class Meta:
        model = Sala
        fields = ["nome", "tipo", "simbolo", "orcamento_mensal", "controlar_dizimos"]
        widgets = {
            "nome": forms.TextInput(
                attrs={"autocomplete": "off", "placeholder": "Ex.: Nosso espaço"}
            ),
            "orcamento_mensal": forms.NumberInput(
                attrs={"min": "0", "step": "0.01", "inputmode": "decimal"}
            ),
        }
        help_texts = {
            "orcamento_mensal": (
                "Esta previsão pode ser zero e não altera nenhum saldo."
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["simbolo"].widget.attrs["data-room-symbol"] = ""
        if not self.instance.pk and not self.is_bound:
            self.initial["simbolo"] = ""

    def clean(self):
        dados = super().clean()
        if not dados.get("tipo"):
            dados["tipo"] = Sala.Tipo.CASAL
        if not dados.get("simbolo"):
            dados["simbolo"] = (
                Sala.Simbolo.BAU
                if dados.get("tipo") == Sala.Tipo.AMIGOS
                else Sala.Simbolo.CORACAO
            )
        return dados


class CodigoConviteForm(forms.Form):
    codigo = forms.CharField(
        label="Código do convite",
        max_length=TAMANHO_CODIGO_CONVITE + 3,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "off",
                "autocapitalize": "characters",
                "placeholder": "Digite o código",
            }
        ),
    )

    def clean_codigo(self):
        codigo = self.cleaned_data["codigo"]
        return codigo.replace("-", "").replace(" ", "").upper()
