from django import forms
from django.contrib.auth import get_user_model

from .models import CartaoCredito, Conta


class ContaForm(forms.ModelForm):
    compartilhar_sala = forms.BooleanField(
        label="Compartilhar esta conta na sala",
        required=False,
        help_text=(
            "O saldo real pode refletir movimentos privados. Os detalhes privados não serão exibidos."
        ),
    )

    class Meta:
        model = Conta
        fields = [
            "tipo",
            "nome",
            "titular",
            "saldo_inicial",
            "data_saldo_inicial",
        ]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: Carteira"}),
            "saldo_inicial": forms.NumberInput(
                attrs={"step": "0.01", "inputmode": "decimal"}
            ),
            "data_saldo_inicial": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
        }
        help_texts = {
            "saldo_inicial": "Este valor é apenas o ponto de partida, não uma receita.",
        }

    def __init__(self, *args, sala=None, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.sala = sala
        self.usuario = usuario
        if sala:
            if not self.instance.pk:
                self.instance.sala = sala
                self.instance.proprietario_usuario = None
            self.fields["titular"].queryset = get_user_model().objects.filter(
                vinculo_sala__sala=sala
            )
            self.fields.pop("compartilhar_sala")
        else:
            if not self.instance.pk:
                self.instance.sala = None
                self.instance.proprietario_usuario = usuario
            self.fields["titular"].queryset = get_user_model().objects.filter(pk=usuario.pk)
            self.fields["titular"].initial = usuario
            if not hasattr(usuario, "vinculo_sala"):
                self.fields.pop("compartilhar_sala")
            elif self.instance.pk:
                self.fields["compartilhar_sala"].initial = bool(
                    self.instance.sala_compartilhada_id
                )


class CartaoCreditoForm(forms.ModelForm):
    compartilhar_sala = forms.BooleanField(
        label="Compartilhar este cartão na sala",
        required=False,
        help_text=(
            "O total real da fatura pode incluir compras privadas, sem revelar seus detalhes."
        ),
    )

    class Meta:
        model = CartaoCredito
        fields = [
            "nome",
            "cor_simbolo",
            "regra_fechamento",
            "dia_fechamento",
            "regra_vencimento",
            "dia_vencimento",
        ]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: Cartão principal"}),
            "cor_simbolo": forms.RadioSelect,
            "regra_fechamento": forms.RadioSelect,
            "dia_fechamento": forms.NumberInput(
                attrs={
                    "min": "1",
                    "max": "31",
                    "inputmode": "numeric",
                    "data-card-fixed-day": "fechamento",
                }
            ),
            "regra_vencimento": forms.RadioSelect,
            "dia_vencimento": forms.NumberInput(
                attrs={
                    "min": "1",
                    "max": "31",
                    "inputmode": "numeric",
                    "data-card-fixed-day": "vencimento",
                }
            ),
        }
        help_texts = {
            "dia_fechamento": "Informe um dia de 1 a 31.",
            "dia_vencimento": (
                "Em meses mais curtos, será usado o último dia disponível."
            ),
        }

    def __init__(self, *args, sala=None, usuario=None, **kwargs):
        if args and args[0] is not None:
            dados = args[0].copy()
            instancia = kwargs.get("instance")
            dados.setdefault(
                "cor_simbolo",
                getattr(instancia, "cor_simbolo", CartaoCredito.CorSimbolo.ROXO),
            )
            dados.setdefault(
                "regra_fechamento",
                getattr(
                    instancia,
                    "regra_fechamento",
                    CartaoCredito.RegraData.DIA_FIXO,
                ),
            )
            dados.setdefault(
                "regra_vencimento",
                getattr(
                    instancia,
                    "regra_vencimento",
                    CartaoCredito.RegraData.DIA_FIXO,
                ),
            )
            args = (dados, *args[1:])
        super().__init__(*args, **kwargs)
        self.sala = sala
        self.usuario = usuario
        if sala:
            if not self.instance.pk:
                self.instance.sala = sala
                self.instance.proprietario_usuario = None
            self.fields.pop("compartilhar_sala")
        else:
            if not self.instance.pk:
                self.instance.sala = None
                self.instance.proprietario_usuario = usuario
            if not hasattr(usuario, "vinculo_sala"):
                self.fields.pop("compartilhar_sala")
            elif self.instance.pk:
                self.fields["compartilhar_sala"].initial = bool(
                    self.instance.sala_compartilhada_id
                )

    def clean(self):
        dados = super().clean()
        if dados.get("regra_fechamento") == CartaoCredito.RegraData.ULTIMO_DIA:
            dados["dia_fechamento"] = None
            self.instance.dia_fechamento = None
        elif not dados.get("dia_fechamento"):
            self.add_error("dia_fechamento", "Informe o dia fixo de fechamento.")

        if dados.get("regra_vencimento") == CartaoCredito.RegraData.ULTIMO_DIA:
            dados["dia_vencimento"] = None
            self.instance.dia_vencimento = None
        elif not dados.get("dia_vencimento"):
            self.add_error("dia_vencimento", "Informe o dia fixo de vencimento.")
        return dados
