"""Rotas principais do projeto financeiro."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("cartoes/", include("cartoes.urls")),
    path("contas/", include("contas.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("entradas/", include("entradas.urls")),
    path("saidas/", include("saidas.urls")),
    path("salas/", include("salas.urls")),
    path("usuarios/", include("usuarios.urls")),
    path("", include("core.urls")),
]

handler403 = "core.views.erro_403"
handler404 = "core.views.erro_404"
handler500 = "core.views.erro_500"
