from django.contrib import admin

from .models import Saida


@admin.register(Saida)
class SaidaAdmin(admin.ModelAdmin):
    list_display = [
        "descricao",
        "valor",
        "responsavel",
        "situacao",
        "vencimento",
        "data_pagamento",
        "conta",
    ]
    list_filter = ["situacao", "custo_vida", "forma_pagamento"]
    search_fields = ["descricao", "responsavel__username", "responsavel__email"]
    readonly_fields = ["chave_idempotencia"]
