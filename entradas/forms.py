import re
import uuid
from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from contas.models import Conta
from core.campos import ValorBrasileiroField

from .models import ConfiguracaoDizimo, DevolucaoDizimo, Entrada, TipoEntrada


class FiltroEntradaForm(forms.Form):
    mes = forms.CharField(
        label="Mês",
        required=False,
        widget=forms.TextInput(attrs={"type": "month"}),
    )
    pessoa = forms.ModelChoiceField(
        label="Pessoa",
        required=False,
        queryset=get_user_model().objects.none(),
        empty_label="Todas as pessoas",
    )
    tipo = forms.ChoiceField(
        label="Tipo",
        required=False,
        choices=[("", "Todos os tipos"), *TipoEntrada.choices],
    )
    situacao = forms.ChoiceField(
        label="Situação",
        required=False,
        choices=[("", "Todas as situações"), *Entrada.Situacao.choices],
    )

    def __init__(self, *args, sala=None, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if sala:
            pessoas = get_user_model().objects.filter(vinculo_sala__sala=sala)
        else:
            pessoas = get_user_model().objects.filter(pk=usuario.pk)
        self.fields["pessoa"].queryset = pessoas

    def clean_mes(self):
        mes = self.cleaned_data["mes"]
        if mes and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", mes):
            raise forms.ValidationError("Informe um mês válido.")
        return mes


class EntradaForm(forms.ModelForm):
    chave_formulario = forms.UUIDField(widget=forms.HiddenInput)
    valor = ValorBrasileiroField(
        label="Valor recebido",
        min_value=Decimal("0.01"),
        max_digits=12,
        decimal_places=2,
        help_text="Informe o valor líquido que realmente recebeu.",
    )
    valor_dizimo_manual = ValorBrasileiroField(
        label="Valor manual",
        required=False,
        min_value=Decimal("0.01"),
        max_digits=12,
        decimal_places=2,
    )
    compartilhar_sala = forms.BooleanField(
        label="Compartilhar na sala",
        required=False,
        help_text="O lançamento continuará sendo seu e também aparecerá no espaço compartilhado.",
    )

    class Meta:
        model = Entrada
        fields = [
            "pessoa",
            "tipo",
            "descricao",
            "valor",
            "situacao",
            "data_prevista",
            "data",
            "observacao",
            "calcular_dizimo",
            "forma_calculo",
            "percentual_dizimo",
            "valor_dizimo_manual",
        ]
        widgets = {
            "descricao": forms.TextInput(attrs={"placeholder": "Ex.: Salário de outubro"}),
            "data": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "data_prevista": forms.DateInput(
                format="%Y-%m-%d", attrs={"type": "date", "data-financial-date": ""}
            ),
            "observacao": forms.TextInput(
                attrs={"placeholder": "Algum detalhe importante (opcional)"}
            ),
            "percentual_dizimo": forms.NumberInput(
                attrs={
                    "min": "0.01",
                    "max": "100",
                    "step": "0.01",
                    "inputmode": "decimal",
                }
            ),
        }
        help_texts = {
            "valor": "Informe o valor líquido que realmente recebeu.",
            "calcular_dizimo": "O valor previsto não será descontado do saldo.",
        }

    def __init__(
        self, *args, sala=None, usuario=None, controla_dizimos=True,
        data_inicial=None, **kwargs
    ):
        kwargs.setdefault("initial", {})
        kwargs["initial"].setdefault("chave_formulario", uuid.uuid4())
        data_padrao = data_inicial or timezone.localdate()
        kwargs["initial"].setdefault(
            "situacao",
            Entrada.Situacao.A_RECEBER
            if data_padrao > timezone.localdate()
            else Entrada.Situacao.RECEBIDA,
        )
        kwargs["initial"].setdefault("data_prevista", data_padrao)
        kwargs["initial"].setdefault(
            "data",
            None if data_padrao > timezone.localdate() else data_padrao,
        )
        super().__init__(*args, **kwargs)
        self.sala = sala
        self.usuario = usuario
        self.controla_dizimos = controla_dizimos
        self.fields["situacao"].required = False
        self.fields["situacao"].widget.attrs["data-financial-status"] = "entrada"
        if sala:
            if not self.instance.pk:
                self.instance.sala = sala
                self.instance.proprietario_usuario = None
            self.fields["pessoa"].queryset = get_user_model().objects.filter(
                vinculo_sala__sala=sala
            )
            self.fields.pop("compartilhar_sala")
        else:
            if not self.instance.pk:
                self.instance.sala = None
                self.instance.proprietario_usuario = usuario
            self.fields["pessoa"].queryset = get_user_model().objects.filter(pk=usuario.pk)
            self.fields["pessoa"].initial = usuario
            if not hasattr(usuario, "vinculo_sala"):
                self.fields.pop("compartilhar_sala")
            else:
                self.fields["compartilhar_sala"].initial = (
                    bool(self.instance.sala_compartilhada_id)
                    if self.instance.pk
                    else usuario.compartilhar_novos_lancamentos
                )
        if not controla_dizimos:
            for campo in (
                "calcular_dizimo",
                "forma_calculo",
                "percentual_dizimo",
                "valor_dizimo_manual",
            ):
                self.fields.pop(campo)

    def clean(self):
        dados = super().clean()
        conta = dados.get("conta_destino")
        if dados.get("compartilhar_sala") and conta:
            vinculo = getattr(self.usuario, "vinculo_sala", None)
            if not vinculo or conta.sala_compartilhada_id != vinculo.sala_id:
                self.add_error(
                    "conta_destino",
                    "Compartilhe primeiro a conta de destino com a sala.",
                )
        situacao = dados.get("situacao")
        if not situacao:
            data_referencia = dados.get("data_prevista") or dados.get("data")
            situacao = (
                Entrada.Situacao.A_RECEBER
                if data_referencia and data_referencia > timezone.localdate()
                else Entrada.Situacao.RECEBIDA
            )
            dados["situacao"] = situacao
            self.instance.situacao = situacao
        if situacao == Entrada.Situacao.A_RECEBER:
            dados["data"] = None
            self.instance.data = None
        elif situacao == Entrada.Situacao.RECEBIDA and not dados.get("data_prevista"):
            dados["data_prevista"] = dados.get("data")
            self.instance.data_prevista = dados.get("data")
        elif situacao == Entrada.Situacao.CANCELADA:
            dados["data"] = None
            self.instance.data = None
        return dados


class RecebimentoEntradaForm(forms.Form):
    data_recebimento = forms.DateField(
        label="Data do recebimento",
        initial=timezone.localdate,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )


class DevolucaoDizimoForm(forms.ModelForm):
    chave_formulario = forms.UUIDField(widget=forms.HiddenInput)
    valor = ValorBrasileiroField(
        label="Valor",
        min_value=Decimal("0.01"),
        max_digits=12,
        decimal_places=2,
        help_text="A devolução reduz o saldo da conta escolhida uma única vez.",
    )

    class Meta:
        model = DevolucaoDizimo
        fields = ["valor", "data", "conta"]
        widgets = {
            "data": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }

    def __init__(self, *args, sala=None, usuario=None, **kwargs):
        kwargs.setdefault("initial", {})
        kwargs["initial"].setdefault("chave_formulario", uuid.uuid4())
        super().__init__(*args, **kwargs)
        if sala:
            contas = Conta.objects.filter(
                Q(sala=sala)
                | Q(
                    sala_compartilhada=sala,
                    proprietario_usuario__vinculo_sala__sala=sala,
                ),
                tipo=Conta.Tipo.DINHEIRO,
            )
        else:
            contas = Conta.objects.filter(
                proprietario_usuario=usuario,
                tipo=Conta.Tipo.DINHEIRO,
            )
        self.fields["conta"].queryset = contas.distinct()


class ConfiguracaoDizimoForm(forms.ModelForm):
    valor_dizimo_manual = ValorBrasileiroField(
        label="Valor manual",
        required=False,
        min_value=Decimal("0.01"),
        max_digits=12,
        decimal_places=2,
    )
    class Meta:
        model = ConfiguracaoDizimo
        fields = [
            "pessoa",
            "tipo_entrada",
            "calcular_dizimo",
            "forma_calculo",
            "percentual_dizimo",
            "valor_dizimo_manual",
        ]
        widgets = {
            "percentual_dizimo": forms.NumberInput(
                attrs={
                    "min": "0.01",
                    "max": "100",
                    "step": "0.01",
                    "inputmode": "decimal",
                }
            ),
            "valor_dizimo_manual": forms.NumberInput(
                attrs={"min": "0.01", "step": "0.01", "inputmode": "decimal"}
            ),
        }

    def __init__(self, *args, sala=None, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.sala = sala
        self.usuario = usuario
        self.instance.sala = sala
        self.instance.proprietario_usuario = None if sala else usuario
        if sala:
            pessoas = get_user_model().objects.filter(vinculo_sala__sala=sala)
        else:
            pessoas = get_user_model().objects.filter(pk=usuario.pk)
            self.fields["pessoa"].initial = usuario
        self.fields["pessoa"].queryset = pessoas

    def clean(self):
        cleaned_data = super().clean()
        pessoa = cleaned_data.get("pessoa")
        tipo_entrada = cleaned_data.get("tipo_entrada")
        if pessoa and tipo_entrada:
            propriedade = (
                {"sala": self.sala}
                if self.sala
                else {"proprietario_usuario": self.usuario}
            )
            repetida = ConfiguracaoDizimo.objects.filter(
                pessoa=pessoa,
                tipo_entrada=tipo_entrada,
                **propriedade,
            ).exclude(pk=self.instance.pk)
            if repetida.exists():
                self.add_error(
                    "tipo_entrada",
                    "Já existe uma configuração para esta pessoa e este tipo.",
                )
        return cleaned_data
