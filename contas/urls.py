from django.urls import path

from . import views


app_name = "contas"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nova/", views.criar_conta, name="criar_conta"),
    path("<int:conta_id>/editar/", views.editar_conta, name="editar_conta"),
    path("cartoes/novo/", views.criar_cartao, name="criar_cartao"),
    path(
        "cartoes/<int:cartao_id>/editar/",
        views.editar_cartao,
        name="editar_cartao",
    ),
]
