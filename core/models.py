from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from contas.models import Conta
from salas.models import Sala

from .atalhos import (
    SIMBOLO_PADRAO,
    SIMBOLOS_ATALHO,
    caminho_do_simbolo,
    categorias_do_tipo,
    simbolo_pertence_ao_tipo,
)


class AtalhoLancamento(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = "entrada", "Entrada"
        SAIDA = "saida", "Saída"

    sala = models.ForeignKey(
        Sala,
        on_delete=models.CASCADE,
        related_name="atalhos_lancamento",
        null=True,
        blank=True,
    )
    proprietario_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="atalhos_lancamento",
        null=True,
        blank=True,
    )
    nome = models.CharField("nome", max_length=60)
    tipo = models.CharField("tipo", max_length=10, choices=Tipo.choices)
    simbolo = models.CharField(
        "símbolo",
        max_length=30,
        choices=[(identificador, dados["nome"]) for identificador, dados in SIMBOLOS_ATALHO.items()],
        default=SIMBOLO_PADRAO,
    )
    categoria = models.CharField("categoria financeira", max_length=30)
    conta_padrao = models.ForeignKey(
        Conta,
        on_delete=models.PROTECT,
        related_name="atalhos_padrao",
        null=True,
        blank=True,
        verbose_name="conta padrão",
    )
    ordem = models.PositiveIntegerField(default=0)
    arquivado = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "atalho de lançamento"
        verbose_name_plural = "atalhos de lançamento"
        ordering = ["tipo", "ordem", "nome", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(sala__isnull=False, proprietario_usuario__isnull=True)
                    | Q(sala__isnull=True, proprietario_usuario__isnull=False)
                ),
                name="atalho_um_proprietario",
            )
        ]

    def clean(self):
        super().clean()
        erros = {}
        if bool(self.sala_id) == bool(self.proprietario_usuario_id):
            erros["sala"] = "O atalho deve pertencer a um único espaço."
        categorias_validas = {
            identificador for identificador, _ in categorias_do_tipo(self.tipo)
        }
        if self.categoria not in categorias_validas:
            erros["categoria"] = "Escolha uma categoria compatível com o tipo do atalho."
        if self.simbolo and not simbolo_pertence_ao_tipo(self.simbolo, self.tipo):
            erros["simbolo"] = "Escolha um símbolo compatível com o tipo do item."
        if self.conta_padrao_id:
            if self.sala_id and not (
                self.conta_padrao.sala_id == self.sala_id
                or self.conta_padrao.sala_compartilhada_id == self.sala_id
            ):
                erros["conta_padrao"] = "A conta deve pertencer ou estar compartilhada com a sala."
            elif (
                self.proprietario_usuario_id
                and self.conta_padrao.proprietario_usuario_id != self.proprietario_usuario_id
            ):
                erros["conta_padrao"] = "Use uma conta do espaço individual."
            elif self.tipo == self.Tipo.ENTRADA:
                conta_de_vale = self.categoria == "vale_alimentacao"
                if conta_de_vale != (self.conta_padrao.tipo == Conta.Tipo.VALE_ALIMENTACAO):
                    erros["conta_padrao"] = "A conta padrão não é compatível com a categoria da entrada."
        if erros:
            raise ValidationError(erros)

    @property
    def caminho_simbolo(self):
        if self.tipo == self.Tipo.ENTRADA and self.categoria == "vale_alimentacao":
            return "dropduo/icons/talheres.png"
        return caminho_do_simbolo(self.simbolo, self.tipo)

    def __str__(self):
        return self.nome
