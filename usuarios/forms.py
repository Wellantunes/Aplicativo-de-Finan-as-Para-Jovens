from django import forms

from .models import Usuario
from .avatar_catalogo import VERSAO_AVATAR_ATUAL
from contas.models import CartaoCredito, Conta


class ConfiguracaoRendaForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ["renda_mensal_prevista"]
        widgets = {
            "renda_mensal_prevista": forms.NumberInput(
                attrs={"min": "0", "step": "0.01", "inputmode": "decimal"}
            )
        }


class ConfiguracaoDizimoInicialForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = [
            "dizimo_automatico",
            "percentual_dizimo_padrao",
            "incluir_vale_no_dizimo",
        ]
        widgets = {
            "percentual_dizimo_padrao": forms.NumberInput(
                attrs={
                    "min": "0",
                    "max": "100",
                    "step": "0.01",
                    "inputmode": "decimal",
                }
            )
        }
        labels = {
            "dizimo_automatico": "Quero controlar dízimos no meu espaço individual",
        }


class AvatarForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = [
            "avatar_v2_base",
            "avatar_v2_pele",
            "avatar_v2_cabelo",
            "avatar_v2_cor_cabelo",
            "avatar_v2_barba",
            "avatar_v2_roupa",
            "avatar_v2_cor_roupa",
        ]

    def clean(self):
        dados = super().clean()
        if (
            dados.get("avatar_v2_roupa") == "camisa_azul"
            and dados.get("avatar_v2_cor_roupa") != "azul"
        ):
            self.add_error(
                "avatar_v2_cor_roupa",
                "A camisa azul não permite escolher outra cor.",
            )
        return dados

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.avatar_versao = VERSAO_AVATAR_ATUAL
        if commit:
            usuario.save()
        return usuario


class ConfiguracaoInicialFinalForm(forms.Form):
    proximo_passo = forms.ChoiceField(
        label="O que deseja fazer agora?",
        choices=[
            ("depois", "Configurar depois"),
            ("conta", "Cadastrar uma conta"),
            ("cartao", "Cadastrar um cartão"),
        ],
        widget=forms.RadioSelect,
        initial="depois",
    )


class PerfilFinanceiroForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = [
            "renda_mensal_prevista",
            "orcamento_mensal_individual",
            "dizimo_automatico",
            "percentual_dizimo_padrao",
            "incluir_vale_no_dizimo",
            "compartilhar_novos_lancamentos",
        ]
        widgets = {
            "renda_mensal_prevista": forms.NumberInput(
                attrs={"min": "0", "step": "0.01", "inputmode": "decimal"}
            ),
            "orcamento_mensal_individual": forms.NumberInput(
                attrs={"min": "0", "step": "0.01", "inputmode": "decimal"}
            ),
            "percentual_dizimo_padrao": forms.NumberInput(
                attrs={
                    "min": "0",
                    "max": "100",
                    "step": "0.01",
                    "inputmode": "decimal",
                }
            ),
        }
        help_texts = {
            "renda_mensal_prevista": "É apenas uma previsão e não altera seu saldo.",
            "orcamento_mensal_individual": "Previsão mensal do seu custo de vida.",
            "compartilhar_novos_lancamentos": (
                "Aplicada somente a novos lançamentos individuais quando você participa de uma sala."
            ),
        }
        labels = {
            "dizimo_automatico": "Controlar dízimos no meu espaço individual",
        }


class CompartilhamentoForm(forms.Form):
    alcance = forms.ChoiceField(
        label="Lançamentos que deseja compartilhar",
        choices=[
            ("nenhum", "Nenhum lançamento agora"),
            ("mes_atual", "Desde o início do mês atual"),
            ("todo_historico", "Todo o histórico"),
        ],
        widget=forms.RadioSelect,
        initial="nenhum",
    )
    contas = forms.ModelMultipleChoiceField(
        label="Contas que a sala poderá utilizar",
        queryset=Conta.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    cartoes = forms.ModelMultipleChoiceField(
        label="Cartões que a sala poderá utilizar",
        queryset=CartaoCredito.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    compartilhar_novos = forms.BooleanField(
        label="Compartilhar novos lançamentos individuais por padrão",
        required=False,
    )

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contas"].queryset = Conta.objects.filter(
            proprietario_usuario=usuario
        )
        self.fields["cartoes"].queryset = CartaoCredito.objects.filter(
            proprietario_usuario=usuario
        )
        if not self.is_bound:
            self.fields["contas"].initial = Conta.objects.filter(
                proprietario_usuario=usuario,
                sala_compartilhada__isnull=False,
            )
            self.fields["cartoes"].initial = CartaoCredito.objects.filter(
                proprietario_usuario=usuario,
                sala_compartilhada__isnull=False,
            )
            self.fields["compartilhar_novos"].initial = (
                usuario.compartilhar_novos_lancamentos
            )
