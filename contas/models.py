from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum

from salas.models import Sala


def data_valida_no_mes(ano, mes, dia_preferido):
    """Usa o ultimo dia do mes quando o dia preferido nao existe."""

    ultimo_dia = monthrange(ano, mes)[1]
    return date(ano, mes, min(dia_preferido, ultimo_dia))


class Conta(models.Model):
    class Tipo(models.TextChoices):
        DINHEIRO = "dinheiro", "Conta em dinheiro"
        VALE_ALIMENTACAO = "vale_alimentacao", "Vale-alimentação"

    sala = models.ForeignKey(
        Sala,
        on_delete=models.CASCADE,
        related_name="contas",
        null=True,
        blank=True,
    )
    proprietario_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="contas_individuais",
        null=True,
        blank=True,
    )
    sala_compartilhada = models.ForeignKey(
        Sala,
        on_delete=models.PROTECT,
        related_name="contas_individuais_compartilhadas",
        null=True,
        blank=True,
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="contas_cadastradas",
        null=True,
        blank=True,
    )
    tipo = models.CharField("tipo", max_length=20, choices=Tipo.choices)
    nome = models.CharField("nome", max_length=100)
    titular = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="contas_como_titular",
    )
    saldo_inicial = models.DecimalField(
        "saldo inicial",
        max_digits=12,
        decimal_places=2,
    )
    data_saldo_inicial = models.DateField("data do saldo inicial")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "conta"
        verbose_name_plural = "contas"
        ordering = ["tipo", "nome", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(sala__isnull=False, proprietario_usuario__isnull=True)
                    | models.Q(sala__isnull=True, proprietario_usuario__isnull=False)
                ),
                name="conta_um_proprietario",
            )
        ]

    def clean(self):
        super().clean()
        erros = {}
        if self.sala_id and self.titular_id and not self.sala.membros.filter(
            usuario_id=self.titular_id
        ).exists():
            erros["titular"] = "O titular deve ser um participante da sala."
        if self.proprietario_usuario_id and self.titular_id != self.proprietario_usuario_id:
            erros["titular"] = "O titular da conta individual deve ser seu proprietário."
        if bool(self.sala_id) == bool(self.proprietario_usuario_id):
            erros["sala"] = "A conta deve possuir um único proprietário."
        if self.sala_compartilhada_id:
            if not self.proprietario_usuario_id:
                erros["sala_compartilhada"] = "Somente contas individuais são compartilhadas."
            elif not self.sala_compartilhada.membros.filter(
                usuario_id=self.proprietario_usuario_id
            ).exists():
                erros["sala_compartilhada"] = "O proprietário deve participar da sala."

        if self.pk:
            tipo_anterior = Conta.objects.filter(pk=self.pk).values_list(
                "tipo",
                flat=True,
            ).first()
            possui_movimentos = (
                self.entradas.exists()
                or self.devolucoes_dizimo.exists()
                or self.saidas.exists()
                or self.pagamentos_fatura.exists()
            )
            if tipo_anterior != self.tipo and possui_movimentos:
                erros["tipo"] = (
                    "O tipo não pode ser alterado porque esta conta já possui movimentos."
                )

        if erros:
            raise ValidationError(erros)

    def __str__(self):
        return self.nome

    @property
    def saldo_atual(self):
        total_entradas = (
            self.entradas.filter(situacao="recebida").aggregate(total=Sum("valor"))[
                "total"
            ]
            or Decimal("0.00")
        )
        total_devolucoes = (
            self.devolucoes_dizimo.aggregate(total=Sum("valor"))["total"]
            or Decimal("0.00")
        )
        total_saidas = (
            self.saidas.filter(situacao="paga").aggregate(total=Sum("valor"))["total"]
            or Decimal("0.00")
        )
        total_faturas = (
            self.pagamentos_fatura.aggregate(total=Sum("valor"))["total"]
            or Decimal("0.00")
        )
        return (
            self.saldo_inicial
            + total_entradas
            - total_devolucoes
            - total_saidas
            - total_faturas
        )


class CartaoCredito(models.Model):
    class RegraData(models.TextChoices):
        DIA_FIXO = "dia_fixo", "Dia fixo"
        ULTIMO_DIA = "ultimo_dia", "Último dia do mês"

    class CorSimbolo(models.TextChoices):
        ROXO = "roxo", "Roxo"
        AMARELO = "amarelo", "Amarelo"
        VERDE = "verde", "Verde"
        AZUL = "azul", "Azul"
        VERMELHO = "vermelho", "Vermelho"
        PRETO = "preto", "Preto"

    sala = models.ForeignKey(
        Sala,
        on_delete=models.CASCADE,
        related_name="cartoes_credito",
        null=True,
        blank=True,
    )
    proprietario_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cartoes_individuais",
        null=True,
        blank=True,
    )
    sala_compartilhada = models.ForeignKey(
        Sala,
        on_delete=models.PROTECT,
        related_name="cartoes_individuais_compartilhados",
        null=True,
        blank=True,
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cartoes_cadastrados",
        null=True,
        blank=True,
    )
    nome = models.CharField("nome", max_length=100)
    cor_simbolo = models.CharField(
        "cor do símbolo",
        max_length=10,
        choices=CorSimbolo.choices,
        default=CorSimbolo.ROXO,
    )
    titular = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cartoes_como_titular",
    )
    regra_fechamento = models.CharField(
        "regra de fechamento",
        max_length=12,
        choices=RegraData.choices,
        default=RegraData.DIA_FIXO,
    )
    dia_fechamento = models.PositiveSmallIntegerField(
        "dia de fechamento",
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        null=True,
        blank=True,
    )
    regra_vencimento = models.CharField(
        "regra de vencimento",
        max_length=12,
        choices=RegraData.choices,
        default=RegraData.DIA_FIXO,
    )
    dia_vencimento = models.PositiveSmallIntegerField(
        "dia de vencimento",
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        null=True,
        blank=True,
    )
    arquivado = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "cartão de crédito"
        verbose_name_plural = "cartões de crédito"
        ordering = ["nome", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(sala__isnull=False, proprietario_usuario__isnull=True)
                    | models.Q(sala__isnull=True, proprietario_usuario__isnull=False)
                ),
                name="cartao_um_proprietario",
            )
        ]

    def clean(self):
        super().clean()
        erros = {}
        if self.sala_id and self.titular_id and not self.sala.membros.filter(
            usuario_id=self.titular_id
        ).exists():
            erros["titular"] = "O titular deve ser um participante da sala."
        if self.proprietario_usuario_id and self.titular_id != self.proprietario_usuario_id:
            erros["titular"] = "O titular do cartão individual deve ser seu proprietário."
        if bool(self.sala_id) == bool(self.proprietario_usuario_id):
            erros["sala"] = "O cartão deve possuir um único proprietário."
        if self.sala_compartilhada_id:
            if not self.proprietario_usuario_id:
                erros["sala_compartilhada"] = "Somente cartões individuais são compartilhados."
            elif not self.sala_compartilhada.membros.filter(
                usuario_id=self.proprietario_usuario_id
            ).exists():
                erros["sala_compartilhada"] = "O proprietário deve participar da sala."
        if self.regra_fechamento == self.RegraData.DIA_FIXO and not self.dia_fechamento:
            erros["dia_fechamento"] = "Informe o dia fixo de fechamento."
        if self.regra_vencimento == self.RegraData.DIA_FIXO and not self.dia_vencimento:
            erros["dia_vencimento"] = "Informe o dia fixo de vencimento."
        if erros:
            raise ValidationError(erros)

    def data_fechamento_no_mes(self, ano, mes):
        if self.regra_fechamento == self.RegraData.ULTIMO_DIA:
            return date(ano, mes, monthrange(ano, mes)[1])
        return data_valida_no_mes(ano, mes, self.dia_fechamento)

    def data_vencimento_no_mes(self, ano, mes):
        if self.regra_vencimento == self.RegraData.ULTIMO_DIA:
            return date(ano, mes, monthrange(ano, mes)[1])
        return data_valida_no_mes(ano, mes, self.dia_vencimento)

    @property
    def texto_fechamento(self):
        if self.regra_fechamento == self.RegraData.ULTIMO_DIA:
            return "Fecha no último dia do mês."
        return f"Fecha todo dia {self.dia_fechamento}."

    @property
    def texto_vencimento(self):
        if self.regra_vencimento == self.RegraData.ULTIMO_DIA:
            return "Vence no último dia do mês."
        return f"Vence todo dia {self.dia_vencimento}."

    @property
    def caminho_simbolo(self):
        return f"dropduo/cards/cartao-{self.cor_simbolo}.svg"

    def __str__(self):
        return self.nome
