import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q, Sum

from contas.models import CartaoCredito, Conta
from salas.models import Sala


class CompraCredito(models.Model):
    sala = models.ForeignKey(
        Sala,
        on_delete=models.CASCADE,
        related_name="compras_credito",
        null=True,
        blank=True,
    )
    proprietario_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="compras_credito_individuais",
        null=True,
        blank=True,
    )
    sala_compartilhada = models.ForeignKey(
        Sala,
        on_delete=models.PROTECT,
        related_name="compras_individuais_compartilhadas",
        null=True,
        blank=True,
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="compras_credito_cadastradas",
        null=True,
        blank=True,
    )
    cartao = models.ForeignKey(
        CartaoCredito,
        on_delete=models.PROTECT,
        related_name="compras",
        verbose_name="cartão",
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="compras_credito",
        verbose_name="responsável",
    )
    descricao = models.CharField("descrição", max_length=150)
    valor_total = models.DecimalField(
        "valor total",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    data_compra = models.DateField("data da compra")
    quantidade_parcelas = models.PositiveSmallIntegerField(
        "quantidade de parcelas",
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
    )
    custo_vida = models.BooleanField("é custo de vida?", default=False)
    chave_idempotencia = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "compra no crédito"
        verbose_name_plural = "compras no crédito"
        ordering = ["-data_compra", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(valor_total__gt=0),
                name="compra_credito_valor_positivo",
            ),
            models.CheckConstraint(
                condition=(
                    Q(sala__isnull=False, proprietario_usuario__isnull=True)
                    | Q(sala__isnull=True, proprietario_usuario__isnull=False)
                ),
                name="compra_credito_um_proprietario",
            ),
        ]

    def clean(self):
        super().clean()
        erros = {}
        if bool(self.sala_id) == bool(self.proprietario_usuario_id):
            erros["sala"] = "A compra deve possuir um único proprietário."
        if self.sala_id and self.cartao_id and not (
            self.cartao.sala_id == self.sala_id
            or self.cartao.sala_compartilhada_id == self.sala_id
        ):
            erros["cartao"] = "O cartão deve pertencer ou estar compartilhado com a sala."
        if self.sala_id and self.responsavel_id and not self.sala.membros.filter(
            usuario_id=self.responsavel_id
        ).exists():
            erros["responsavel"] = "O responsável deve ser participante da sala."
        if (
            self.proprietario_usuario_id
            and self.responsavel_id != self.proprietario_usuario_id
        ):
            erros["responsavel"] = "A compra individual pertence ao próprio usuário."
        if self.proprietario_usuario_id and self.cartao_id:
            if self.cartao.proprietario_usuario_id != self.proprietario_usuario_id:
                erros["cartao"] = "Use um cartão individual do proprietário."
        if self.sala_compartilhada_id:
            if not self.proprietario_usuario_id:
                erros["sala_compartilhada"] = "Somente compras individuais são compartilhadas."
            elif not self.sala_compartilhada.membros.filter(
                usuario_id=self.proprietario_usuario_id
            ).exists():
                erros["sala_compartilhada"] = "O proprietário deve participar da sala."
            elif self.cartao_id and (
                self.cartao.sala_compartilhada_id != self.sala_compartilhada_id
            ):
                erros["cartao"] = "Compartilhe também o cartão utilizado com a sala."
        if erros:
            raise ValidationError(erros)

    def __str__(self):
        return self.descricao


class Fatura(models.Model):
    cartao = models.ForeignKey(
        CartaoCredito,
        on_delete=models.CASCADE,
        related_name="faturas",
        verbose_name="cartão",
    )
    ano_referencia = models.PositiveSmallIntegerField("ano de referência")
    mes_referencia = models.PositiveSmallIntegerField(
        "mês de referência",
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    data_fechamento = models.DateField("data de fechamento")
    data_vencimento = models.DateField("data de vencimento")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "fatura"
        verbose_name_plural = "faturas"
        ordering = ["-ano_referencia", "-mes_referencia", "cartao__nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["cartao", "ano_referencia", "mes_referencia"],
                name="fatura_unica_por_cartao_mes",
            )
        ]

    def clean(self):
        super().clean()
        erros = {}
        if self.data_fechamento and self.data_vencimento:
            if self.data_vencimento <= self.data_fechamento:
                erros["data_vencimento"] = (
                    "O vencimento deve ser posterior ao fechamento."
                )
        if self.data_vencimento and (
            self.ano_referencia != self.data_vencimento.year
            or self.mes_referencia != self.data_vencimento.month
        ):
            erros["data_vencimento"] = (
                "O mês de referência da fatura deve ser o mês do vencimento."
            )
        if erros:
            raise ValidationError(erros)

    @property
    def valor_total(self):
        return self.parcelas.aggregate(total=Sum("valor"))["total"] or Decimal("0.00")

    @property
    def esta_paga(self):
        return hasattr(self, "pagamento")

    @property
    def referencia_formatada(self):
        return f"{self.mes_referencia:02d}/{self.ano_referencia}"

    def __str__(self):
        return f"{self.cartao} — {self.referencia_formatada}"


class Parcela(models.Model):
    compra = models.ForeignKey(
        CompraCredito,
        on_delete=models.CASCADE,
        related_name="parcelas",
    )
    fatura = models.ForeignKey(
        Fatura,
        on_delete=models.PROTECT,
        related_name="parcelas",
    )
    numero = models.PositiveSmallIntegerField("número da parcela")
    valor = models.DecimalField("valor", max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "parcela"
        verbose_name_plural = "parcelas"
        ordering = ["numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["compra", "numero"],
                name="numero_parcela_unico_por_compra",
            ),
            models.CheckConstraint(
                condition=Q(valor__gt=0),
                name="parcela_valor_positivo",
            ),
        ]

    def __str__(self):
        return f"{self.compra} — {self.numero}/{self.compra.quantidade_parcelas}"


class PagamentoFatura(models.Model):
    fatura = models.OneToOneField(
        Fatura,
        on_delete=models.PROTECT,
        related_name="pagamento",
    )
    conta = models.ForeignKey(
        Conta,
        on_delete=models.PROTECT,
        related_name="pagamentos_fatura",
        verbose_name="conta utilizada",
        null=True,
        blank=True,
    )
    valor = models.DecimalField("valor pago", max_digits=12, decimal_places=2)
    data_pagamento = models.DateField("data do pagamento")
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pagamentos_fatura_registrados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "pagamento de fatura"
        verbose_name_plural = "pagamentos de fatura"
        constraints = [
            models.CheckConstraint(
                condition=Q(valor__gt=0),
                name="pagamento_fatura_valor_positivo",
            )
        ]

    def clean(self):
        super().clean()
        erros = {}
        if self.conta_id:
            if self.conta.tipo != Conta.Tipo.DINHEIRO:
                erros["conta"] = "A fatura deve ser paga por uma conta em dinheiro."
            elif self.fatura.cartao.sala_id and not (
                self.conta.sala_id == self.fatura.cartao.sala_id
                or self.conta.sala_compartilhada_id == self.fatura.cartao.sala_id
            ):
                erros["conta"] = "A conta deve pertencer ou estar compartilhada com a sala."
            elif (
                self.fatura.cartao.proprietario_usuario_id
                and self.conta.proprietario_usuario_id
                != self.fatura.cartao.proprietario_usuario_id
            ):
                erros["conta"] = "Use uma conta individual do titular do cartão."
        if erros:
            raise ValidationError(erros)

    def __str__(self):
        return f"Pagamento de {self.fatura}"
