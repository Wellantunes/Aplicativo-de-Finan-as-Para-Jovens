from django.urls import path

from . import views


app_name = "usuarios"

urlpatterns = [
    path("avatar/", views.editar_avatar, name="avatar"),
    path("perfil/", views.perfil, name="perfil"),
    path("perfil/compartilhamento/", views.compartilhamento, name="compartilhamento"),
    path("configuracao/renda/", views.configuracao_renda, name="configuracao_renda"),
    path("configuracao/dizimo/", views.configuracao_dizimo, name="configuracao_dizimo"),
    path("configuracao/final/", views.configuracao_final, name="configuracao_final"),
]
