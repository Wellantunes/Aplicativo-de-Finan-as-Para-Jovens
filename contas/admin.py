from django.contrib import admin

from .models import CartaoCredito, Conta


@admin.register(Conta)
class ContaAdmin(admin.ModelAdmin):
    list_display = [
        "nome",
        "tipo",
        "sala",
        "titular",
        "saldo_inicial",
        "data_saldo_inicial",
    ]
    list_filter = ["tipo"]
    search_fields = ["nome", "sala__nome", "titular__username", "titular__email"]


@admin.register(CartaoCredito)
class CartaoCreditoAdmin(admin.ModelAdmin):
    list_display = [
        "nome",
        "sala",
        "titular",
        "cor_simbolo",
        "regra_fechamento",
        "dia_fechamento",
        "regra_vencimento",
        "dia_vencimento",
        "arquivado",
    ]
    list_filter = ["arquivado", "cor_simbolo", "regra_fechamento", "regra_vencimento"]
    search_fields = ["nome", "sala__nome", "titular__username", "titular__email"]
