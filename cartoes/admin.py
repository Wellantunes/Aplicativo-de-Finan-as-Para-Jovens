from django.contrib import admin

from .models import CompraCredito, Fatura, PagamentoFatura, Parcela


class ParcelaInline(admin.TabularInline):
    model = Parcela
    extra = 0
    readonly_fields = ["fatura", "numero", "valor"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CompraCredito)
class CompraCreditoAdmin(admin.ModelAdmin):
    list_display = [
        "descricao",
        "cartao",
        "responsavel",
        "valor_total",
        "data_compra",
        "quantidade_parcelas",
    ]
    list_filter = ["custo_vida", "cartao"]
    search_fields = ["descricao", "responsavel__username", "responsavel__email"]
    readonly_fields = ["chave_idempotencia"]
    inlines = [ParcelaInline]


@admin.register(Fatura)
class FaturaAdmin(admin.ModelAdmin):
    list_display = [
        "cartao",
        "mes_referencia",
        "ano_referencia",
        "data_fechamento",
        "data_vencimento",
        "esta_paga",
    ]
    list_filter = ["cartao", "ano_referencia"]


@admin.register(PagamentoFatura)
class PagamentoFaturaAdmin(admin.ModelAdmin):
    list_display = ["fatura", "valor", "conta", "data_pagamento", "registrado_por"]
    readonly_fields = ["fatura", "valor", "conta", "data_pagamento", "registrado_por"]

    def has_add_permission(self, request):
        return False
