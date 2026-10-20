from datetime import date
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from core.espacos import sala_ativa
from core.periodos import mes_ativo

from .calculos import calcular_dashboard
from .forms import FiltroDashboardForm


def _mover_mes(ano, mes, quantidade):
    """Retorna o ano e o mês após avançar ou voltar a quantidade informada."""

    indice = (ano * 12) + (mes - 1) + quantidade
    novo_ano, indice_mes = divmod(indice, 12)
    return novo_ano, indice_mes + 1


def _url_com_filtros(nome_rota, mes, responsavel="", ancora=""):
    parametros = {"mes": mes}
    if responsavel:
        parametros["responsavel"] = responsavel
    url = f"{reverse(nome_rota)}?{urlencode(parametros)}"
    return f"{url}#{ancora}" if ancora else url


@login_required
def mensal(request):
    if not request.user.avatar_concluido:
        return redirect("usuarios:avatar")
    sala = sala_ativa(request)
    mes_atual, _, _ = mes_ativo(request, request.GET.get("mes"))
    parametros_filtro = request.GET.copy()
    parametros_filtro.setdefault("mes", mes_atual)
    filtro = FiltroDashboardForm(
        parametros_filtro,
        sala=sala,
        usuario=request.user,
    )
    responsavel = None
    somente_sala = False
    escolha_responsavel = ""
    if filtro.is_valid():
        mes_selecionado = filtro.cleaned_data["mes"]
        ano, mes = (int(parte) for parte in mes_selecionado.split("-"))
        escolha_responsavel = filtro.cleaned_data.get("responsavel") or ""
        if escolha_responsavel == "sala":
            somente_sala = True
        elif escolha_responsavel.startswith("usuario:"):
            usuario_id = int(escolha_responsavel.split(":", 1)[1])
            if sala and sala.membros.filter(usuario_id=usuario_id).exists():
                responsavel = get_user_model().objects.get(pk=usuario_id)
    else:
        hoje = timezone.localdate()
        ano, mes = hoje.year, hoje.month
        mes_selecionado = hoje.strftime("%Y-%m")

    ano_anterior, mes_anterior = _mover_mes(ano, mes, -1)
    ano_seguinte, mes_seguinte = _mover_mes(ano, mes, 1)
    filtro_responsavel = escolha_responsavel if sala else ""
    parametros_lista = {"mes": mes_selecionado}
    if responsavel:
        parametros_lista["pessoa"] = responsavel.pk
    link_entradas = f"{reverse('entradas:lista')}?{urlencode(parametros_lista)}"
    link_dizimos = f"{link_entradas}#dizimos"

    parametros_saidas = {"mes": mes_selecionado}
    if responsavel:
        parametros_saidas["responsavel"] = responsavel.pk
    parametros_custo_vida = {**parametros_saidas, "custo_vida": "1"}
    link_custo_vida = (
        f"{reverse('saidas:lista')}?{urlencode(parametros_custo_vida)}#titulo-custo-vida"
    )
    link_saidas = f"{reverse('saidas:lista')}?{urlencode(parametros_saidas)}"

    contexto = calcular_dashboard(
        sala,
        ano,
        mes,
        responsavel,
        usuario=request.user,
        somente_sala=somente_sala,
    )
    contexto.update({
        "sala": sala,
        "titulo_espaco": sala.nome if sala else "Meu espaço",
        "filtro": filtro,
        "espaco_individual": sala is None,
        "data_mes": date(ano, mes, 1),
        "mes_selecionado": mes_selecionado,
        "mes_anterior_url": _url_com_filtros(
            "dashboard:mensal",
            f"{ano_anterior:04d}-{mes_anterior:02d}",
            filtro_responsavel,
        ),
        "mes_seguinte_url": _url_com_filtros(
            "dashboard:mensal",
            f"{ano_seguinte:04d}-{mes_seguinte:02d}",
            filtro_responsavel,
        ),
        "link_entradas": link_entradas,
        "link_dizimos": link_dizimos,
        "link_custo_vida": link_custo_vida,
        "link_saidas": link_saidas,
        "link_vale": (
            f"{reverse('core:registrar_vale')}?{urlencode({'mes': mes_selecionado})}"
        ),
        "percentual_custo_vida": min(
            100,
            round(
                (contexto["custo_vida"] / contexto["orcamento_custo_vida"]) * 100
            ),
        ) if contexto["orcamento_custo_vida"] else 0,
    })
    return render(request, "dashboard/mensal.html", contexto)
