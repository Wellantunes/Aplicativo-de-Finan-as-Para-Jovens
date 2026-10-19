from django.urls import path

from .views import mensal


app_name = "dashboard"

urlpatterns = [
    path("", mensal, name="mensal"),
]
