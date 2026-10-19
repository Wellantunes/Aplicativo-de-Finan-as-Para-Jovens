from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("manifest.webmanifest", views.manifesto, name="manifesto"),
    path("lancamentos/", views.lancamentos, name="lancamentos"),
    path("lancamentos/vale/registrar/", views.registrar_vale, name="registrar_vale"),
    path("lancamentos/atalhos/", views.gerenciar_atalhos, name="gerenciar_atalhos"),
    path("lancamentos/atalhos/novo/", views.criar_atalho, name="criar_atalho"),
    path(
        "lancamentos/atalhos/<int:atalho_id>/editar/",
        views.editar_atalho,
        name="editar_atalho",
    ),
    path(
        "lancamentos/atalhos/<int:atalho_id>/arquivar/",
        views.alternar_arquivo_atalho,
        name="alternar_arquivo_atalho",
    ),
    path(
        "lancamentos/atalhos/<int:atalho_id>/mover/",
        views.mover_atalho,
        name="mover_atalho",
    ),
    path(
        "lancamentos/atalhos/<int:atalho_id>/registrar/",
        views.registrar_atalho,
        name="registrar_atalho",
    ),
    path("entrar/", views.HomeView.as_view(), name="entrar"),
    path("criar-conta/", views.criar_conta, name="criar_conta"),
    path("recuperar-senha/", views.recuperar_senha, name="recuperar_senha"),
    path("", views.HomeView.as_view(), name="home"),
]
