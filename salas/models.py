import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


ALFABETO_CONVITE = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TAMANHO_CODIGO_CONVITE = 8


def gerar_codigo_convite():
    """Gera um codigo curto sem caracteres que costumam ser confundidos."""

    return "".join(
        secrets.choice(ALFABETO_CONVITE) for _ in range(TAMANHO_CODIGO_CONVITE)
    )


def validade_padrao_convite():
    return timezone.now() + timedelta(hours=24)


class Sala(models.Model):
    class Tipo(models.TextChoices):
        CASAL = "casal", "Casal"
        AMIGOS = "amigos", "Amigos"

    class Simbolo(models.TextChoices):
        CORACAO = "coracao", "Coração"
        BAU = "bau", "Baú"

    nome = models.CharField("nome", max_length=100)
    tipo = models.CharField(
        "tipo",
        max_length=10,
        choices=Tipo.choices,
        default=Tipo.CASAL,
    )
    simbolo = models.CharField(
        "símbolo decorativo",
        max_length=10,
        choices=Simbolo.choices,
        default=Simbolo.CORACAO,
    )
    orcamento_mensal = models.DecimalField(
        "orçamento mensal",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    controlar_dizimos = models.BooleanField(
        "esta sala vai controlar dízimos?",
        default=False,
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="salas_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "sala"
        verbose_name_plural = "salas"
        constraints = [
            models.CheckConstraint(
                condition=Q(orcamento_mensal__gte=0),
                name="sala_orcamento_nao_negativo",
            )
        ]

    def __str__(self):
        return self.nome


class MembroSala(models.Model):
    sala = models.ForeignKey(
        Sala,
        on_delete=models.CASCADE,
        related_name="membros",
    )
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vinculo_sala",
    )
    entrou_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "membro da sala"
        verbose_name_plural = "membros da sala"
        ordering = ["entrou_em", "pk"]

    def __str__(self):
        return f"{self.usuario} em {self.sala}"


class ConviteSala(models.Model):
    sala = models.ForeignKey(
        Sala,
        on_delete=models.CASCADE,
        related_name="convites",
    )
    codigo = models.CharField(
        "código",
        max_length=TAMANHO_CODIGO_CONVITE,
        unique=True,
        editable=False,
        default=gerar_codigo_convite,
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="convites_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField(default=validade_padrao_convite)
    usado_em = models.DateTimeField(null=True, blank=True)
    usado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="convites_utilizados",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "convite da sala"
        verbose_name_plural = "convites da sala"
        ordering = ["-criado_em"]

    @property
    def esta_ativo(self):
        return self.usado_em is None and self.expira_em > timezone.now()

    def __str__(self):
        return f"Convite {self.codigo} para {self.sala}"
