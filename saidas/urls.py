from django.urls import path

from . import views


app_name = "saidas"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nova/", views.criar, name="criar"),
    path("<int:saida_id>/editar/", views.editar, name="editar"),
    path("<int:saida_id>/excluir/", views.excluir, name="excluir"),
    path("<int:saida_id>/pagar/", views.pagar, name="pagar"),
]
