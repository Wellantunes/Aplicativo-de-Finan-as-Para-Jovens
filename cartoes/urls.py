from django.urls import path

from . import views


app_name = "cartoes"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("<int:cartao_id>/", views.detalhe_cartao, name="detalhe_cartao"),
    path(
        "<int:cartao_id>/arquivar/",
        views.alternar_arquivo_cartao,
        name="alternar_arquivo_cartao",
    ),
    path(
        "<int:cartao_id>/compras/nova/",
        views.criar_compra_cartao,
        name="criar_compra_cartao",
    ),
    path(
        "<int:cartao_id>/compras/previa/",
        views.previa_fatura,
        name="previa_fatura",
    ),
    path("compras/nova/", views.criar_compra_view, name="criar_compra"),
    path("compras/<int:compra_id>/editar/", views.editar_compra, name="editar_compra"),
    path("compras/<int:compra_id>/excluir/", views.excluir_compra_view, name="excluir_compra"),
    path("faturas/<int:fatura_id>/", views.detalhe_fatura, name="detalhe_fatura"),
    path(
        "faturas/<int:fatura_id>/ajustar/",
        views.ajustar_fatura,
        name="ajustar_fatura",
    ),
    path("faturas/<int:fatura_id>/pagar/", views.pagar_fatura_view, name="pagar_fatura"),
]
