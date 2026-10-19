from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from decimal import Decimal

from .avatar_catalogo import (
    BARBA_CHOICES,
    BASE_CHOICES,
    CABELO_CHOICES,
    COR_CABELO_CHOICES,
    COR_ROUPA_CHOICES,
    PELE_CHOICES,
    ROUPA_CHOICES,
)


class Usuario(AbstractUser):
    """Usuario customizado, pronto para futuras formas de autenticacao."""

    class PeleAvatar(models.TextChoices):
        CLARA = "clara", "Clara"
        MEDIA = "media", "Média"
        ESCURA = "escura", "Escura"

    class CabeloAvatar(models.TextChoices):
        PRETO = "preto", "Preto"
        CASTANHO = "castanho", "Castanho"
        LOIRO = "loiro", "Loiro"
        RUIVO = "ruivo", "Ruivo"
        RASPADO = "raspado", "Raspado"

    class OlhosAvatar(models.TextChoices):
        CASTANHOS = "castanhos", "Castanhos"
        AZUIS = "azuis", "Azuis"
        VERDES = "verdes", "Verdes"

    class SobrancelhasAvatar(models.TextChoices):
        SUAVES = "suaves", "Suaves"
        MARCADAS = "marcadas", "Marcadas"

    class BarbaAvatar(models.TextChoices):
        SEM_BARBA = "sem_barba", "Sem barba"
        BARBA = "barba", "Barba"
        CAVANHAQUE = "cavanhaque", "Cavanhaque"

    class OculosAvatar(models.TextChoices):
        SEM_OCULOS = "sem_oculos", "Sem óculos"
        REDONDOS = "redondos", "Redondos"
        QUADRADOS = "quadrados", "Quadrados"

    class RoupaAvatar(models.TextChoices):
        AZUL = "azul", "Azul"
        CORAL = "coral", "Coral"
        DOURADA = "dourada", "Dourada"

    foto_url = models.URLField("foto de perfil", max_length=500, blank=True)
    renda_mensal_prevista = models.DecimalField(
        "renda líquida mensal prevista",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    orcamento_mensal_individual = models.DecimalField(
        "orçamento mensal individual",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    dizimo_automatico = models.BooleanField(default=False)
    percentual_dizimo_padrao = models.DecimalField(
        "percentual padrão do dízimo",
        max_digits=5,
        decimal_places=2,
        default=Decimal("10.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("100.00")),
        ],
    )
    incluir_vale_no_dizimo = models.BooleanField(default=False)
    compartilhar_novos_lancamentos = models.BooleanField(default=False)
    configuracao_inicial_concluida = models.BooleanField(default=False)
    avatar_concluido = models.BooleanField(default=False)
    avatar_pele = models.CharField(
        "pele",
        max_length=10,
        choices=PeleAvatar.choices,
        default=PeleAvatar.MEDIA,
    )
    avatar_cabelo = models.CharField(
        "cabelo",
        max_length=10,
        choices=CabeloAvatar.choices,
        default=CabeloAvatar.CASTANHO,
    )
    avatar_olhos = models.CharField(
        "olhos",
        max_length=10,
        choices=OlhosAvatar.choices,
        default=OlhosAvatar.CASTANHOS,
    )
    avatar_sobrancelhas = models.CharField(
        "sobrancelhas",
        max_length=10,
        choices=SobrancelhasAvatar.choices,
        default=SobrancelhasAvatar.SUAVES,
    )
    avatar_barba = models.CharField(
        "barba",
        max_length=12,
        choices=BarbaAvatar.choices,
        default=BarbaAvatar.SEM_BARBA,
    )
    avatar_oculos = models.CharField(
        "óculos",
        max_length=12,
        choices=OculosAvatar.choices,
        default=OculosAvatar.SEM_OCULOS,
    )
    avatar_roupa = models.CharField(
        "roupa",
        max_length=10,
        choices=RoupaAvatar.choices,
        default=RoupaAvatar.AZUL,
    )
    avatar_versao = models.PositiveSmallIntegerField(default=1)
    avatar_v2_base = models.CharField(
        "base",
        max_length=12,
        choices=BASE_CHOICES,
        default="masculina",
    )
    avatar_v2_pele = models.CharField(
        "tom de pele",
        max_length=15,
        choices=PELE_CHOICES,
        default="media",
    )
    avatar_v2_cabelo = models.CharField(
        "cabelo",
        max_length=15,
        choices=CABELO_CHOICES,
        default="curto",
    )
    avatar_v2_cor_cabelo = models.CharField(
        "cor do cabelo",
        max_length=15,
        choices=COR_CABELO_CHOICES,
        default="castanho",
    )
    avatar_v2_barba = models.CharField(
        "barba",
        max_length=15,
        choices=BARBA_CHOICES,
        default="sem_barba",
    )
    avatar_v2_roupa = models.CharField(
        "roupa",
        max_length=15,
        choices=ROUPA_CHOICES,
        default="camiseta",
    )
    avatar_v2_cor_roupa = models.CharField(
        "cor da roupa",
        max_length=15,
        choices=COR_ROUPA_CHOICES,
        default="creme",
    )

    @property
    def usa_avatar_v2(self):
        return self.avatar_versao == 2

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def __str__(self):
        return self.get_full_name() or self.username
