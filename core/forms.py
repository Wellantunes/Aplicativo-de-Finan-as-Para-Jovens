import uuid
from decimal import Decimal

from django import forms
from django.utils import timezone

from entradas.models import Entrada
from saidas.models import Saida

from .atalhos import categoria_padrao_do_item, simbolos_do_tipo
from .campos import ValorBrasileiroField
from .models import AtalhoLancamento


class AtalhoLancamentoForm(forms.ModelForm):
    class Meta:
        model = AtalhoLancamento
        fields = ["nome", "simbolo"]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: Mercado"}),
            "simbolo": forms.RadioSelect,
        }

    def __init__(self, *args, tipo, sala=None, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tipo not in AtalhoLancamento.Tipo.values:
            raise ValueError("Tipo de item inválido.")
        self.tipo = tipo
        self.sala = sala
        self.usuario = usuario
        self.instance.tipo = tipo
        if not self.instance.pk:
            self.instance.sala = sala
            self.instance.proprietario_usuario = None if sala else usuario
        self.fields["simbolo"].choices = [
            (identificador, dados["nome"])
            for identificador, dados in simbolos_do_tipo(tipo).items()
        ]
        self.fields["simbolo"].error_messages["invalid_choice"] = (
            "Escolha um símbolo compatível com o tipo do item."
        )

    def clean(self):
        dados = super().clean()
        simbolo = dados.get("simbolo")
        self.instance.tipo = self.tipo
        self.instance.categoria = categoria_padrao_do_item(self.tipo, simbolo or "")
        self.instance.conta_padrao = None
        return dados


class RegistroRapidoBaseForm(forms.Form):
    chave_formulario = forms.UUIDField(widget=forms.HiddenInput)
    mes_consulta = forms.CharField(required=False, widget=forms.HiddenInput)
    valor = ValorBrasileiroField(
        label="Valor",
        min_value=Decimal("0.01"),
        max_digits=12,
        decimal_places=2,
        widget=forms.TextInput(attrs={"class": "quick-value-input"}),
    )
    data = forms.DateField(
        label="Data prevista ou efetiva",
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={"type": "date", "data-financial-date": ""},
        ),
    )
    observacao = forms.CharField(
        label="Observação (opcional)",
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Algum detalhe importante"}),
    )

    def __init__(
        self, *args, atalho, sala=None, usuario=None, data_inicial=None, **kwargs
    ):
        kwargs.setdefault("initial", {})
        kwargs["initial"].setdefault("chave_formulario", uuid.uuid4())
        kwargs["initial"].setdefault("data", data_inicial or timezone.localdate())
        super().__init__(*args, **kwargs)
        self.atalho = atalho
        self.sala = sala
        self.usuario = usuario

class RegistroRapidoEntradaForm(RegistroRapidoBaseForm):
    situacao = forms.ChoiceField(
        label="Situação",
        required=False,
        choices=[
            (Entrada.Situacao.RECEBIDA, "Recebida"),
            (Entrada.Situacao.A_RECEBER, "A receber"),
        ],
        widget=forms.RadioSelect(attrs={"data-financial-status": "entrada"}),
    )

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("initial", {}).setdefault("situacao", Entrada.Situacao.RECEBIDA)
        super().__init__(*args, **kwargs)

    def clean(self):
        dados = super().clean()
        if dados.get("data") and dados["data"] > timezone.localdate():
            dados["situacao"] = Entrada.Situacao.A_RECEBER
        elif not dados.get("situacao"):
            dados["situacao"] = Entrada.Situacao.RECEBIDA
        return dados


class RegistroRapidoValeForm(RegistroRapidoBaseForm):
    descricao = forms.CharField(
        label="Nome ou descrição",
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Ex.: Vale iFood"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data"].label = "Data"
        self.order_fields(
            ["chave_formulario", "mes_consulta", "valor", "descricao", "data"]
        )


class RegistroRapidoSaidaForm(RegistroRapidoBaseForm):
    situacao = forms.ChoiceField(
        label="Situação",
        required=False,
        choices=[
            (Saida.Situacao.PAGA, "Paga"),
            (Saida.Situacao.PENDENTE, "A pagar"),
        ],
        widget=forms.RadioSelect(attrs={"data-financial-status": "saida"}),
    )

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("initial", {}).setdefault("situacao", Saida.Situacao.PAGA)
        super().__init__(*args, **kwargs)

    def clean(self):
        dados = super().clean()
        if dados.get("data") and dados["data"] > timezone.localdate():
            dados["situacao"] = Saida.Situacao.PENDENTE
        elif not dados.get("situacao"):
            dados["situacao"] = Saida.Situacao.PAGA
        return dados
