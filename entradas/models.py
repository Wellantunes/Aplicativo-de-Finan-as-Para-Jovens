import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q, Sum

from contas.models import Conta
from salas.models import Sala


CENTAVOS = Decimal("0.01")


class TipoEntrada(models.TextChoices):
    SALARIO = "salario", "Salário"
    EXTRA = "extra", "Extra"
    SEGUNDO_EMPREGO = "segundo_emprego", "Segundo emprego"
    FGTS = "fgts", "FGTS"
    DECIMO_TERCEIRO = "decimo_terceiro", "Décimo terceiro"
    VALE_ALIMENTACAO = "vale_alimentacao", "Vale-alimentação"
    OUTROS = "outros", "Outros"


class FormaCalculoDizimo(models.TextChoices):
    PERCENTUAL = "percentual", "Percentual sobre a entrada"
    VALOR_MANUAL = "valor_manual", "Valor manual"


def calcular_dizimo(valor, calcular, forma, percentual=None, valor_manual=None):
    if not calcular:
        return Decimal("0.00")
    if forma == FormaCalculoDizimo.PERCENTUAL and percentual is not None:
        return (valor * percentual / Decimal("100")).quantize(
            CENTAVOS,
            rounding=ROUND_HALF_UP,
        )
    if forma == FormaCalculoDizimo.VALOR_MANUAL and valor_manual is not None:
        return valor_manual.quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    return Decimal("0.00")


def validar_campos_dizimo(instancia):
    erros = {}
    if not instancia.calcular_dizimo:
        return erros

    if instancia.forma_calculo == FormaCalculoDizimo.PERCENTUAL:
        if instancia.percentual_dizimo is None:
            erros["percentual_dizimo"] = "Informe o percentual do dízimo."
    elif instancia.forma_calculo == FormaCalculoDizimo.VALOR_MANUAL:
        if instancia.valor_dizimo_manual is None:
            erros["valor_dizimo_manual"] = "Informe o valor manual do dízimo."
    else:
        erros["forma_calculo"] = "Escolha como o dízimo será calculado."
    return erros


class ConfiguracaoDizimo(models.Model):
    sala = models.ForeignKey(
        Sala,
        on_delete=models.CASCADE,
        related_name="configuracoes_dizimo",
        null=True,
        blank=True,
    )
    proprietario_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="configuracoes_dizimo_individuais",
        null=True,
        blank=True,
    )
    pessoa = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="configuracoes_dizimo",
    )
    tipo_entrada = models.CharField(
        "tipo de entrada",
        max_length=30,
        choices=TipoEntrada.choices,
    )
    calcular_dizimo = models.BooleanField("calcular dízimo?", default=False)
    forma_calculo = models.CharField(
        "forma de cálculo",
        max_length=20,
        choices=FormaCalculoDizimo.choices,
        blank=True,
    )
    percentual_dizimo = models.DecimalField(
        "percentual",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("100"))],
    )
    valor_dizimo_manual = models.DecimalField(
        "valor manual",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    class Meta:
        verbose_name = "configuração de dízimo"
        verbose_name_plural = "configurações de dízimo"
        ordering = ["pessoa__first_name", "pessoa__username", "tipo_entrada"]
        constraints = [
            models.UniqueConstraint(
                fields=["sala", "pessoa", "tipo_entrada"],
                name="configuracao_dizimo_unica_por_pessoa_tipo",
                condition=Q(sala__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["proprietario_usuario", "tipo_entrada"],
                name="config_dizimo_individual_unica_tipo",
                condition=Q(proprietario_usuario__isnull=False),
            ),
            models.CheckConstraint(
                condition=(
                    Q(sala__isnull=False, proprietario_usuario__isnull=True)
                    | Q(sala__isnull=True, proprietario_usuario__isnull=False)
                ),
                name="config_dizimo_um_proprietario",
            ),
        ]

    def clean(self):
        super().clean()
        erros = validar_campos_dizimo(self)
        if bool(self.sala_id) == bool(self.proprietario_usuario_id):
            erros["sala"] = "A configuração deve possuir um único proprietário."
        if self.sala_id and self.pessoa_id and not self.sala.membros.filter(
            usuario_id=self.pessoa_id
        ).exists():
            erros["pessoa"] = "A pessoa deve ser participante da sala."
        if self.proprietario_usuario_id and self.pessoa_id != self.proprietario_usuario_id:
            erros["pessoa"] = "A configuração individual pertence ao próprio usuário."
        if erros:
            raise ValidationError(erros)

    def __str__(self):
        return f"{self.pessoa} — {self.get_tipo_entrada_display()}"


class Entrada(models.Model):
    class Situacao(models.TextChoices):
        A_RECEBER = "a_receber", "A receber"
        RECEBIDA = "recebida", "Recebida"
        CANCELADA = "cancelada", "Cancelada"

    sala = models.ForeignKey(
        Sala,
        on_delete=models.CASCADE,
        related_name="entradas",
        null=True,
        blank=True,
    )
    proprietario_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="entradas_individuais",
        null=True,
        blank=True,
    )
    sala_compartilhada = models.ForeignKey(
        Sala,
        on_delete=models.PROTECT,
        related_name="entradas_individuais_compartilhadas",
        null=True,
        blank=True,
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="entradas_cadastradas",
        null=True,
        blank=True,
    )
    pessoa = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="entradas_recebidas",
        verbose_name="pessoa que recebeu",
    )
    tipo = models.CharField("tipo", max_length=30, choices=TipoEntrada.choices)
    descricao = models.CharField("descrição", max_length=150)
    valor = models.DecimalField(
        "valor recebido",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    situacao = models.CharField(
        "situação",
        max_length=12,
        choices=Situacao.choices,
        default=Situacao.RECEBIDA,
    )
    data_prevista = models.DateField("data prevista", null=True, blank=True)
    data = models.DateField("data do recebimento", null=True, blank=True)
    conta_destino = models.ForeignKey(
        Conta,
        on_delete=models.PROTECT,
        related_name="entradas",
        verbose_name="conta de destino",
        null=True,
        blank=True,
    )
    calcular_dizimo = models.BooleanField("calcular dízimo?", default=False)
    forma_calculo = models.CharField(
        "forma de cálculo",
        max_length=20,
        choices=FormaCalculoDizimo.choices,
        blank=True,
    )
    percentual_dizimo = models.DecimalField(
        "percentual",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("100"))],
    )
    valor_dizimo_manual = models.DecimalField(
        "valor manual",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    dizimo_previsto = models.DecimalField(
        "dízimo previsto",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        editable=False,
    )
    observacao = models.CharField("observação", max_length=200, blank=True)
    atalho = models.ForeignKey(
        "core.AtalhoLancamento",
        on_delete=models.SET_NULL,
        related_name="entradas",
        null=True,
        blank=True,
    )
    categoria_atalho = models.CharField(max_length=30, blank=True, editable=False)
    chave_idempotencia = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "entrada"
        verbose_name_plural = "entradas"
        ordering = ["-data", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(valor__gt=0), name="entrada_valor_positivo"),
            models.CheckConstraint(
                condition=Q(dizimo_previsto__gte=0),
                name="entrada_dizimo_nao_negativo",
            ),
            models.CheckConstraint(
                condition=(
                    Q(sala__isnull=False, proprietario_usuario__isnull=True)
                    | Q(sala__isnull=True, proprietario_usuario__isnull=False)
                ),
                name="entrada_um_proprietario",
            ),
        ]

    def clean(self):
        super().clean()
        erros = validar_campos_dizimo(self)

        if bool(self.sala_id) == bool(self.proprietario_usuario_id):
            erros["sala"] = "A entrada deve possuir um único proprietário."

        if self.sala_id and self.pessoa_id and not self.sala.membros.filter(
            usuario_id=self.pessoa_id
        ).exists():
            erros["pessoa"] = "A pessoa deve ser participante da sala."
        if self.proprietario_usuario_id and self.pessoa_id != self.proprietario_usuario_id:
            erros["pessoa"] = "A entrada individual pertence ao próprio usuário."
        if self.sala_compartilhada_id:
            if not self.proprietario_usuario_id:
                erros["sala_compartilhada"] = "Somente entradas individuais são compartilhadas."
            elif not self.sala_compartilhada.membros.filter(
                usuario_id=self.proprietario_usuario_id
            ).exists():
                erros["sala_compartilhada"] = "O proprietário deve participar da sala."

        if self.situacao == self.Situacao.A_RECEBER:
            if not self.data_prevista:
                erros["data_prevista"] = "Informe a data prevista da entrada."
            if self.data:
                erros["data"] = "Uma entrada a receber não possui data de recebimento."
        elif self.situacao == self.Situacao.RECEBIDA:
            if not self.data:
                erros["data"] = "Informe a data do recebimento."
            if not self.data_prevista:
                self.data_prevista = self.data
        elif (
            self.situacao == self.Situacao.CANCELADA
            and self.pk
            and self.devolucoes.exists()
        ):
            erros["situacao"] = "Uma entrada com devolução de dízimo não pode ser cancelada."

        if self.conta_destino_id:
            if self.sala_id and not (
                self.conta_destino.sala_id == self.sala_id
                or self.conta_destino.sala_compartilhada_id == self.sala_id
            ):
                erros["conta_destino"] = "A conta deve pertencer ou estar compartilhada com a sala."
            elif (
                self.proprietario_usuario_id
                and self.conta_destino.proprietario_usuario_id
                != self.proprietario_usuario_id
            ):
                erros["conta_destino"] = "Use uma conta individual do proprietário."
            elif (
                self.sala_compartilhada_id
                and self.conta_destino.sala_compartilhada_id
                != self.sala_compartilhada_id
            ):
                erros["conta_destino"] = "Compartilhe também a conta de destino com a sala."
            elif (
                self.tipo == TipoEntrada.VALE_ALIMENTACAO
                and self.conta_destino.tipo != Conta.Tipo.VALE_ALIMENTACAO
            ):
                erros["conta_destino"] = "Vale-alimentação deve entrar em uma conta de vale."
            elif (
                self.tipo != TipoEntrada.VALE_ALIMENTACAO
                and self.conta_destino.tipo != Conta.Tipo.DINHEIRO
            ):
                erros["conta_destino"] = "Esta entrada deve ir para uma conta em dinheiro."

        if erros:
            raise ValidationError(erros)

    def save(self, *args, **kwargs):
        self.dizimo_previsto = calcular_dizimo(
            self.valor,
            self.calcular_dizimo,
            self.forma_calculo,
            self.percentual_dizimo,
            self.valor_dizimo_manual,
        )
        super().save(*args, **kwargs)

    @property
    def valor_devolvido(self):
        total = self.devolucoes.aggregate(total=Sum("valor"))["total"]
        return total or Decimal("0.00")

    @property
    def dizimo_restante(self):
        return max(self.dizimo_previsto - self.valor_devolvido, Decimal("0.00"))

    @property
    def data_referencia(self):
        """Mês financeiro da entrada, preservando compatibilidade histórica."""

        return self.data_prevista or self.data

    @property
    def caminho_simbolo(self):
        """Escolhe o ícone pela classificação financeira da entrada."""

        if self.tipo == TipoEntrada.VALE_ALIMENTACAO:
            return "dropduo/icons/talheres.png"
        if self.atalho_id:
            return self.atalho.caminho_simbolo
        return "dropduo/icons/bau.png"

    def __str__(self):
        return self.descricao


class DevolucaoDizimo(models.Model):
    entrada = models.ForeignKey(
        Entrada,
        on_delete=models.PROTECT,
        related_name="devolucoes",
    )
    valor = models.DecimalField(
        "valor devolvido",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    data = models.DateField("data da devolução")
    conta = models.ForeignKey(
        Conta,
        on_delete=models.PROTECT,
        related_name="devolucoes_dizimo",
        verbose_name="conta utilizada",
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="devolucoes_dizimo_registradas",
    )
    chave_idempotencia = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "devolução de dízimo"
        verbose_name_plural = "devoluções de dízimo"
        ordering = ["data", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(valor__gt=0),
                name="devolucao_dizimo_valor_positivo",
            )
        ]

    def clean(self):
        super().clean()
        erros = {}
        if self.entrada_id and self.conta_id:
            if self.conta.tipo != Conta.Tipo.DINHEIRO:
                erros["conta"] = "A devolução deve sair de uma conta em dinheiro."
            elif self.entrada.sala_id and not (
                self.conta.sala_id == self.entrada.sala_id
                or self.conta.sala_compartilhada_id == self.entrada.sala_id
            ):
                erros["conta"] = "A conta deve pertencer ou estar compartilhada com a sala."
            elif (
                self.entrada.proprietario_usuario_id
                and self.conta.proprietario_usuario_id
                != self.entrada.proprietario_usuario_id
            ):
                erros["conta"] = "Use uma conta individual do proprietário."
            elif (
                self.entrada.sala_compartilhada_id
                and self.conta.sala_compartilhada_id
                != self.entrada.sala_compartilhada_id
            ):
                erros["conta"] = "Compartilhe também a conta usada na devolução."
        if erros:
            raise ValidationError(erros)

    def __str__(self):
        return f"R$ {self.valor} — {self.entrada}"
