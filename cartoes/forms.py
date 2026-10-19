import uuid
from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from contas.models import CartaoCredito, Conta

from .models import CompraCredito, Fatura


class CompraCreditoForm(forms.ModelForm):
    chave_formulario = forms.UUIDField(widget=forms.HiddenInput)
    compartilhar_sala = forms.BooleanField(
        label="Compartilhar na sala",
        required=False,
        help_text="A compra continuará sendo sua e também aparecerá no espaço compartilhado.",
    )

    class Meta:
        model = CompraCredito
        fields = [
            "cartao",
            "responsavel",
            "descricao",
            "valor_total",
            "data_compra",
            "quantidade_parcelas",
            "custo_vida",
        ]
        widgets = {
            "descricao": forms.TextInput(attrs={"placeholder": "Ex.: mercado"}),
            "valor_total": forms.NumberInput(
                attrs={"min": "0.01", "step": "0.01", "inputmode": "decimal"}
            ),
            "data_compra": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "quantidade_parcelas": forms.NumberInput(
                attrs={"min": "1", "max": "60", "inputmode": "numeric"}
            ),
        }

    def __init__(self, *args, sala=None, usuario=None, **kwargs):
        kwargs.setdefault("initial", {})
        kwargs["initial"].setdefault("chave_formulario", uuid.uuid4())
        super().__init__(*args, **kwargs)
        self.sala = sala
        self.usuario = usuario
        if sala:
            if not self.instance.pk:
                self.instance.sala = sala
                self.instance.proprietario_usuario = None
            self.fields["cartao"].queryset = CartaoCredito.objects.filter(
                Q(sala=sala)
                | Q(
                    sala_compartilhada=sala,
                    proprietario_usuario__vinculo_sala__sala=sala,
                )
            ).distinct()
            self.fields["responsavel"].queryset = get_user_model().objects.filter(
                vinculo_sala__sala=sala
            )
            self.fields.pop("compartilhar_sala")
        else:
            if not self.instance.pk:
                self.instance.sala = None
                self.instance.proprietario_usuario = usuario
            self.fields["cartao"].queryset = CartaoCredito.objects.filter(
                proprietario_usuario=usuario
            )
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
        cartao = cleaned_data.get("cartao")
        if cleaned_data.get("compartilhar_sala") and cartao:
            vinculo = getattr(self.usuario, "vinculo_sala", None)
            if not vinculo or cartao.sala_compartilhada_id != vinculo.sala_id:
                self.add_error(
                    "cartao",
                    "Compartilhe primeiro o cartão utilizado com a sala.",
                )
        return cleaned_data


class PagamentoFaturaForm(forms.Form):
    data_pagamento = forms.DateField(
        label="Data do pagamento",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    conta = forms.ModelChoiceField(
        label="Conta utilizada",
        queryset=Conta.objects.none(),
        required=False,
        empty_label="Não vincular a uma conta",
        help_text=(
            "Opcional. Sem uma conta, o pagamento apenas marca a fatura como paga "
            "e não altera saldos bancários."
        ),
    )

    def __init__(self, *args, sala=None, usuario=None, cartao=None, **kwargs):
        super().__init__(*args, **kwargs)
        if cartao and cartao.proprietario_usuario_id:
            self.fields["conta"].queryset = Conta.objects.filter(
                proprietario_usuario=cartao.proprietario_usuario,
                tipo=Conta.Tipo.DINHEIRO,
            )
        elif sala:
            self.fields["conta"].queryset = Conta.objects.filter(
                Q(sala=sala)
                | Q(
                    sala_compartilhada=sala,
                    proprietario_usuario__vinculo_sala__sala=sala,
                ),
                tipo=Conta.Tipo.DINHEIRO,
            ).distinct()
        else:
            self.fields["conta"].queryset = Conta.objects.filter(
                proprietario_usuario=usuario,
                tipo=Conta.Tipo.DINHEIRO,
            )


class CompraRapidaCartaoForm(forms.Form):
    chave_formulario = forms.UUIDField(widget=forms.HiddenInput)
    descricao = forms.CharField(
        label="Descrição",
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Ex.: Pizza"}),
    )
    valor_total = forms.DecimalField(
        label="Valor",
        min_value=Decimal("0.01"),
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={"min": "0.01", "step": "0.01", "inputmode": "decimal"}
        ),
    )
    data_compra = forms.DateField(
        label="Data da compra",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    alterar_fatura = forms.BooleanField(
        label="Alterar fatura",
        required=False,
        help_text="Use apenas quando o banco processar a compra em outro ciclo.",
    )
    fatura_destino = forms.ModelChoiceField(
        label="Fatura de destino",
        queryset=Fatura.objects.none(),
        required=False,
        empty_label="Selecione uma fatura",
    )

    def __init__(self, *args, cartao, **kwargs):
        kwargs.setdefault("initial", {})
        kwargs["initial"].setdefault("chave_formulario", uuid.uuid4())
        super().__init__(*args, **kwargs)
        self.cartao = cartao
        self.fields["fatura_destino"].queryset = (
            Fatura.objects.filter(cartao=cartao, pagamento__isnull=True)
            .order_by("data_fechamento")
        )
        self.fields["fatura_destino"].label_from_instance = (
            lambda fatura: (
                f"Fecha {fatura.data_fechamento:%d/%m/%Y} · "
                f"vence {fatura.data_vencimento:%d/%m/%Y}"
            )
        )

    def clean(self):
        dados = super().clean()
        if dados.get("alterar_fatura") and not dados.get("fatura_destino"):
            self.add_error("fatura_destino", "Escolha a fatura de destino.")
        if not dados.get("alterar_fatura"):
            dados["fatura_destino"] = None
        return dados


class FaturaDatasForm(forms.ModelForm):
    confirmar_mudanca_mes = forms.BooleanField(
        label="Confirmo a mudança do mês da fatura",
        required=False,
    )
    confirmar_compras_fora_ciclo = forms.BooleanField(
        label="Manter as compras listadas nesta fatura por enquanto",
        required=False,
    )

    class Meta:
        model = Fatura
        fields = ["data_fechamento", "data_vencimento"]
        widgets = {
            "data_fechamento": forms.DateInput(
                format="%Y-%m-%d", attrs={"type": "date"}
            ),
            "data_vencimento": forms.DateInput(
                format="%Y-%m-%d", attrs={"type": "date"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mes_original = (
            self.instance.ano_referencia,
            self.instance.mes_referencia,
        )
        self.compras_afetadas = CompraCredito.objects.none()

    def clean(self):
        dados = super().clean()
        fechamento = dados.get("data_fechamento")
        vencimento = dados.get("data_vencimento")
        if not fechamento or not vencimento:
            return dados

        if self.instance.esta_paga and (
            fechamento != self.instance.data_fechamento
            or vencimento != self.instance.data_vencimento
        ):
            raise forms.ValidationError(
                "Uma fatura paga não pode ter suas datas financeiras alteradas."
            )
        if vencimento <= fechamento:
            self.add_error(
                "data_vencimento", "O vencimento deve ser posterior ao fechamento."
            )

        outras = Fatura.objects.filter(cartao=self.instance.cartao).exclude(
            pk=self.instance.pk
        )
        anterior = outras.filter(
            data_fechamento__lt=self.instance.data_fechamento
        ).order_by("-data_fechamento").first()
        seguinte = outras.filter(
            data_fechamento__gt=self.instance.data_fechamento
        ).order_by("data_fechamento").first()
        if anterior and fechamento <= anterior.data_fechamento:
            self.add_error(
                "data_fechamento",
                "O fechamento deve ficar depois da fatura anterior.",
            )
        if seguinte and fechamento >= seguinte.data_fechamento:
            self.add_error(
                "data_fechamento",
                "O fechamento deve ficar antes da próxima fatura.",
            )

        if outras.filter(
            ano_referencia=vencimento.year,
            mes_referencia=vencimento.month,
        ).exists():
            self.add_error(
                "data_vencimento",
                "Já existe outra fatura deste cartão no mês informado.",
            )

        if (vencimento.year, vencimento.month) != self.mes_original and not dados.get(
            "confirmar_mudanca_mes"
        ):
            self.add_error(
                "confirmar_mudanca_mes",
                "Confirme que os indicadores passarão a usar o novo mês de vencimento.",
            )
        self.instance.ano_referencia = vencimento.year
        self.instance.mes_referencia = vencimento.month

        limite_inferior = anterior.data_fechamento if anterior else None
        compras = CompraCredito.objects.filter(parcelas__fatura=self.instance).distinct()
        compras_afetadas = compras.filter(data_compra__gt=fechamento)
        if limite_inferior:
            compras_afetadas = (
                compras.filter(data_compra__lte=limite_inferior)
                | compras_afetadas
            ).distinct()
        self.compras_afetadas = compras_afetadas
        if compras_afetadas.exists() and not dados.get("confirmar_compras_fora_ciclo"):
            self.add_error(
                "confirmar_compras_fora_ciclo",
                "Revise as compras afetadas abaixo e confirme para manter seus vínculos.",
            )
        return dados
