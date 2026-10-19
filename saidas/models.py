import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from contas.models import Conta
from salas.models import Sala


class Saida(models.Model):
    class Situacao(models.TextChoices):
        PENDENTE = "pendente", "A pagar"
        PAGA = "paga", "Paga"
        CANCELADA = "cancelada", "Cancelada"

    class FormaPagamento(models.TextChoices):
        PIX = "pix", "Pix"
        DEBITO = "debito", "Débito"
        DINHEIRO = "dinheiro", "Dinheiro"
        VALE_ALIMENTACAO = "vale_alimentacao", "Vale-alimentação"

    sala = models.ForeignKey(
        Sala,
        on_delete=models.CASCADE,
        related_name="saidas",
        null=True,
        blank=True,
    )
    proprietario_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="saidas_individuais",
        null=True,
        blank=True,
    )
    sala_compartilhada = models.ForeignKey(
        Sala,
        on_delete=models.PROTECT,
        related_name="saidas_individuais_compartilhadas",
        null=True,
        blank=True,
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="saidas_cadastradas",
        null=True,
        blank=True,
    )
    descricao = models.CharField("descrição", max_length=150)
    valor = models.DecimalField(
        "valor",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="saidas_sob_responsabilidade",
        verbose_name="responsável",
    )
    custo_vida = models.BooleanField("é custo de vida?", default=False)
    situacao = models.CharField(
        "situação",
        max_length=10,
        choices=Situacao.choices,
        default=Situacao.PENDENTE,
    )
    vencimento = models.DateField("vencimento", null=True, blank=True)
    data_pagamento = models.DateField("data do pagamento", null=True, blank=True)
    forma_pagamento = models.CharField(
        "forma de pagamento",
        max_length=20,
        choices=FormaPagamento.choices,
        blank=True,
    )
    conta = models.ForeignKey(
        Conta,
        on_delete=models.PROTECT,
        related_name="saidas",
        verbose_name="conta utilizada",
        null=True,
        blank=True,
    )
    observacao = models.CharField("observação", max_length=200, blank=True)
    atalho = models.ForeignKey(
        "core.AtalhoLancamento",
        on_delete=models.SET_NULL,
        related_name="saidas",
        null=True,
        blank=True,
    )
    categoria_atalho = models.CharField(max_length=30, blank=True, editable=False)
    chave_idempotencia = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "saída"
        verbose_name_plural = "saídas"
        ordering = ["-data_pagamento", "vencimento", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(valor__gt=0), name="saida_valor_positivo"),
            models.CheckConstraint(
                condition=(
                    Q(sala__isnull=False, proprietario_usuario__isnull=True)
                    | Q(sala__isnull=True, proprietario_usuario__isnull=False)
                ),
                name="saida_um_proprietario",
            ),
        ]

    def clean(self):
        super().clean()
        erros = {}

        if bool(self.sala_id) == bool(self.proprietario_usuario_id):
            erros["sala"] = "A saída deve possuir um único proprietário."

        if self.sala_id and self.responsavel_id and not self.sala.membros.filter(
            usuario_id=self.responsavel_id
        ).exists():
            erros["responsavel"] = "O responsável deve ser participante da sala."
        if (
            self.proprietario_usuario_id
            and self.responsavel_id != self.proprietario_usuario_id
        ):
            erros["responsavel"] = "A saída individual pertence ao próprio usuário."
        if self.sala_compartilhada_id:
            if not self.proprietario_usuario_id:
                erros["sala_compartilhada"] = "Somente saídas individuais são compartilhadas."
            elif not self.sala_compartilhada.membros.filter(
                usuario_id=self.proprietario_usuario_id
            ).exists():
                erros["sala_compartilhada"] = "O proprietário deve participar da sala."

        if self.situacao == self.Situacao.PENDENTE:
            if not self.vencimento:
                erros["vencimento"] = "Informe o vencimento da saída pendente."
            if self.data_pagamento or self.forma_pagamento or self.conta_id:
                erros["situacao"] = (
                    "Uma saída pendente não pode possuir dados de pagamento."
                )

        if self.situacao == self.Situacao.PAGA:
            if not self.data_pagamento:
                erros["data_pagamento"] = "Informe a data do pagamento."
            if self.conta_id and not self.forma_pagamento:
                erros["forma_pagamento"] = "Informe a forma de pagamento da conta vinculada."
            if self.forma_pagamento and not self.conta_id:
                erros["conta"] = "Informe a conta vinculada a esta forma de pagamento."

        if self.situacao == self.Situacao.CANCELADA and (
            self.data_pagamento or self.forma_pagamento or self.conta_id
        ):
            erros["situacao"] = "Uma saída cancelada não pode possuir dados de pagamento."

        if self.conta_id:
            if self.sala_id and not (
                self.conta.sala_id == self.sala_id
                or self.conta.sala_compartilhada_id == self.sala_id
            ):
                erros["conta"] = "A conta deve pertencer ou estar compartilhada com a sala."
            elif (
                self.proprietario_usuario_id
                and self.conta.proprietario_usuario_id
                != self.proprietario_usuario_id
            ):
                erros["conta"] = "Use uma conta individual do proprietário."
            elif (
                self.sala_compartilhada_id
                and self.conta.sala_compartilhada_id
                != self.sala_compartilhada_id
            ):
                erros["conta"] = "Compartilhe também a conta utilizada com a sala."
            elif (
                self.forma_pagamento == self.FormaPagamento.VALE_ALIMENTACAO
                and self.conta.tipo != Conta.Tipo.VALE_ALIMENTACAO
            ):
                erros["conta"] = "Pagamento com vale deve usar uma conta de vale."
            elif (
                self.forma_pagamento != self.FormaPagamento.VALE_ALIMENTACAO
                and self.conta.tipo != Conta.Tipo.DINHEIRO
            ):
                erros["conta"] = (
                    "Pix, débito e dinheiro devem usar uma conta em dinheiro."
                )

        if erros:
            raise ValidationError(erros)

    @property
    def data_referencia_custo_vida(self):
        return self.data_referencia

    @property
    def data_referencia(self):
        """Mês financeiro da saída, preservando compatibilidade histórica."""

        return self.vencimento or self.data_pagamento

    def __str__(self):
        return self.descricao
