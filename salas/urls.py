from django.urls import path

from . import views


app_name = "salas"

urlpatterns = [
    path("", views.minha_sala, name="minha_sala"),
    path("voltar-ao-meu-espaco/", views.voltar_individual, name="voltar_individual"),
    path("criar/", views.criar_sala, name="criar"),
    path("entrar/", views.informar_codigo, name="entrar"),
    path(
        "convites/<str:codigo>/confirmar/",
        views.confirmar_entrada,
        name="confirmar_entrada",
    ),
    path("<int:sala_id>/", views.detalhe_sala, name="detalhe"),
    path(
        "<int:sala_id>/configuracoes/",
        views.configurar_sala,
        name="configurar",
    ),
    path("<int:sala_id>/acessar/", views.entrar_espaco, name="entrar_espaco"),
    path(
        "<int:sala_id>/convite/",
        views.gerar_convite,
        name="gerar_convite",
    ),
]
