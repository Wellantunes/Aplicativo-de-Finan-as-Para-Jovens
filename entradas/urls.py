from django.urls import path

from . import views


app_name = "entradas"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nova/", views.criar, name="criar"),
    path("<int:entrada_id>/editar/", views.editar, name="editar"),
    path("<int:entrada_id>/excluir/", views.excluir, name="excluir"),
    path("<int:entrada_id>/devolver/", views.devolver, name="devolver"),
    path("<int:entrada_id>/receber/", views.receber, name="receber"),
    path("configuracoes/", views.lista_configuracoes, name="configuracoes"),
    path(
        "configuracoes/nova/",
        views.criar_configuracao,
        name="criar_configuracao",
    ),
    path(
        "configuracoes/<int:configuracao_id>/editar/",
        views.editar_configuracao,
        name="editar_configuracao",
    ),
]
