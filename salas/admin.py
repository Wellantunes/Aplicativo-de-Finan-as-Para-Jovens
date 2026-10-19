from django.contrib import admin

from .models import ConviteSala, MembroSala, Sala


class MembroSalaInline(admin.TabularInline):
    model = MembroSala
    extra = 0
    readonly_fields = ["entrou_em"]


@admin.register(Sala)
class SalaAdmin(admin.ModelAdmin):
    list_display = ["nome", "orcamento_mensal", "criado_por", "criado_em"]
    search_fields = ["nome", "criado_por__username", "criado_por__email"]
    inlines = [MembroSalaInline]


@admin.register(ConviteSala)
class ConviteSalaAdmin(admin.ModelAdmin):
    list_display = ["codigo", "sala", "expira_em", "usado_em", "usado_por"]
    search_fields = ["codigo", "sala__nome"]
    readonly_fields = ["codigo", "criado_em", "usado_em", "usado_por"]
