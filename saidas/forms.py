import re
import uuid
from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.campos import ValorBrasileiroField
from .models import Saida


class SaidaForm(forms.ModelForm):
    chave_formulario = forms.UUIDField(widget=forms.HiddenInput)
    valor = ValorBrasileiroField(
        label="Valor",
        min_value=Decimal("0.01"),
        max_digits=12,
        decimal_places=2,
    )
    compartilhar_sala = forms.BooleanField(
        label="Compartilhar na sala",
        required=False,
        help_text="A saída continuará sendo sua e também aparecerá no espaço compartilhado.",
    )

    class Meta:
        model = Saida
        fields = [
            "descricao",
            "valor",
            "responsavel",
            "custo_vida",
            "situacao",
            "vencimento",
            "data_pagamento",
            "observacao",
        ]
        widgets = {
            "descricao": forms.TextInput(
                attrs={"placeholder": "Ex.: mercado, aluguel ou almoço"}
            ),
            "vencimento": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "data_pagamento": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
            "observacao": forms.TextInput(
                attrs={"placeholder": "Algum detalhe importante (opcional)"}
            ),
        }

    def __init__(self, *args, sala=None, usuario=None, data_inicial=None, **kwargs):
        kwargs.setdefault("initial", {})
        kwargs["initial"].setdefault("chave_formulario", uuid.uuid4())
        kwargs["initial"].setdefault("situacao", Saida.Situacao.PAGA)
        data_padrao = data_inicial or timezone.localdate()
        kwargs["initial"].setdefault("vencimento", data_padrao)
        kwargs["initial"].setdefault("data_pagamento", data_padrao)
        super().__init__(*args, **kwargs)
        self.sala = sala
        self.usuario = usuario
        if sala:
            if not self.instance.pk:
                self.instance.sala = sala
                self.instance.proprietario_usuario = None
            self.fields["responsavel"].queryset = get_user_model().objects.filter(
                vinculo_sala__sala=sala
            )
            self.fields.pop("compartilhar_sala")
        else:
            if not self.instance.pk:
                self.instance.sala = None
                self.instance.proprietario_usuario = usuario
            self.fields["responsavel"].queryset = get_user_model().objects.filter(
                pk=usuario.pk
            )
            self.fields["responsavel"].initial = usuario
            if not hasattr(usuario, "vinculo_sala"):
                self.fields.pop("compartilhar_sala")
            else:
                self.fields["compartilhar_sala"].initial = (
                    bool(self.instance.sala_compartilhada_id)
                    if self.instance.pk
                    else usuario.compartilhar_novos_lancamentos
                )

    def clean(self):
        cleaned_data = super().clean()
        conta = cleaned_data.get("conta")
        if cleaned_data.get("compartilhar_sala") and conta:
            vinculo = getattr(self.usuario, "vinculo_sala", None)
            if not vinculo or conta.sala_compartilhada_id != vinculo.sala_id:
                self.add_error(
                    "conta",
                    "Compartilhe primeiro a conta utilizada com a sala.",
                )
        if cleaned_data.get("situacao") == Saida.Situacao.PENDENTE:
            cleaned_data["data_pagamento"] = None
            self.instance.data_pagamento = None
            self.instance.forma_pagamento = ""
            self.instance.conta = None
        elif cleaned_data.get("situacao") == Saida.Situacao.CANCELADA:
            cleaned_data["vencimento"] = (
                cleaned_data.get("vencimento")
                or cleaned_data.get("data_pagamento")
                or self.instance.vencimento
                or self.instance.data_pagamento
            )
            cleaned_data["data_pagamento"] = None
            self.instance.vencimento = cleaned_data["vencimento"]
            self.instance.data_pagamento = None
            self.instance.forma_pagamento = ""
            self.instance.conta = None
        return cleaned_data


class PagamentoSaidaForm(forms.Form):
    data_pagamento = forms.DateField(
        label="Data do pagamento",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )


class FiltroSaidaForm(forms.Form):
    mes = forms.CharField(
        label="Mês",
        required=False,
        widget=forms.TextInput(attrs={"type": "month"}),
    )
    responsavel = forms.ModelChoiceField(
        label="Responsável",
        required=False,
        queryset=get_user_model().objects.none(),
        empty_label="Todas as pessoas",
    )
    situacao = forms.ChoiceField(
        label="Situação",
        required=False,
        choices=[("", "Todas as situações"), *Saida.Situacao.choices],
    )

    def __init__(self, *args, sala=None, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if sala:
            self.fields["responsavel"].queryset = get_user_model().objects.filter(
                vinculo_sala__sala=sala
            )
        else:
            self.fields["responsavel"].queryset = get_user_model().objects.filter(
                pk=usuario.pk
            )

    def clean_mes(self):
        mes = self.cleaned_data["mes"]
        if mes and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", mes):
            raise forms.ValidationError("Informe um mês válido.")
        return mes
