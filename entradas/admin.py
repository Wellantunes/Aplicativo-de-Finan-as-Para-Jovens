from django.contrib import admin

from .models import ConfiguracaoDizimo, DevolucaoDizimo, Entrada


class DevolucaoDizimoInline(admin.TabularInline):
    model = DevolucaoDizimo
    extra = 0
    readonly_fields = ["registrado_por", "chave_idempotencia", "criado_em"]


@admin.register(Entrada)
class EntradaAdmin(admin.ModelAdmin):
    list_display = [
        "descricao",
        "tipo",
        "pessoa",
        "valor",
        "data",
        "conta_destino",
        "dizimo_previsto",
    ]
    list_filter = ["tipo", "calcular_dizimo"]
    search_fields = ["descricao", "pessoa__username", "pessoa__email"]
    readonly_fields = ["dizimo_previsto", "chave_idempotencia"]
    inlines = [DevolucaoDizimoInline]


@admin.register(ConfiguracaoDizimo)
class ConfiguracaoDizimoAdmin(admin.ModelAdmin):
    list_display = ["pessoa", "tipo_entrada", "calcular_dizimo", "forma_calculo"]
    list_filter = ["tipo_entrada", "calcular_dizimo"]
