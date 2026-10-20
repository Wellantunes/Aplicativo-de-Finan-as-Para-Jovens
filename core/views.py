import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import formats
from django.views.generic import TemplateView
from django.views.decorators.http import require_GET, require_POST

from core.espacos import definir_espaco_individual, sala_ativa
from core.espacos import recursos_disponiveis
from contas.models import CartaoCredito
from entradas.models import Entrada
from saidas.models import Saida

from .atalhos import CATALOGOS_SIMBOLOS
from .forms import (
    AtalhoLancamentoForm,
    RegistroRapidoEntradaForm,
    RegistroRapidoSaidaForm,
    RegistroRapidoValeForm,
)
from .models import AtalhoLancamento
from .periodos import data_inicial_do_mes, mes_ativo
from .services import (
    registrar_entrada_por_atalho,
    registrar_saida_por_atalho,
    registrar_vale_rapido,
)


class HomeView(TemplateView):
    template_name = "auth/entrar.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            definir_espaco_individual(request)
            if not request.user.avatar_concluido:
                return redirect("usuarios:avatar")
            if not request.user.configuracao_inicial_concluida:
                return redirect("usuarios:configuracao_renda")
            return redirect("dashboard:mensal")

        return super().get(request, *args, **kwargs)


@require_GET
def criar_conta(request):
    if request.user.is_authenticated:
        return redirect("core:home")
    return render(request, "auth/criar_conta.html")


@require_GET
def recuperar_senha(request):
    if request.user.is_authenticated:
        return redirect("core:home")
    return render(request, "auth/recuperar_senha.html")


@login_required
def lancamentos(request):
    sala = sala_ativa(request)
    controla_dizimos = sala.controlar_dizimos if sala else request.user.dizimo_automatico
    tipo = request.GET.get("tipo", AtalhoLancamento.Tipo.SAIDA)
    if tipo not in AtalhoLancamento.Tipo.values:
        tipo = AtalhoLancamento.Tipo.SAIDA
    busca = request.GET.get("busca", "").strip()
    mes, _, _ = mes_ativo(request, request.GET.get("mes"))

    atalhos_do_tipo = _atalhos_do_espaco(request).filter(tipo=tipo)
    atalhos = atalhos_do_tipo.filter(arquivado=False)
    if busca:
        atalhos = atalhos.filter(nome__icontains=busca)
    mostrar_vale = tipo == AtalhoLancamento.Tipo.ENTRADA and (
        not busca or busca.casefold() in "vale-alimentação".casefold()
    )
    cartoes = CartaoCredito.objects.none()
    if tipo == AtalhoLancamento.Tipo.SAIDA:
        cartoes = recursos_disponiveis(
            CartaoCredito.objects.filter(arquivado=False), request
        ).select_related("titular")
        if busca:
            cartoes = cartoes.filter(nome__icontains=busca)
    return render(
        request,
        "core/lancamentos.html",
        {
            "atalhos": atalhos,
            "atalhos_arquivados": atalhos_do_tipo.filter(arquivado=True),
            "busca": busca,
            "controla_dizimos": controla_dizimos,
            "mes_consulta": mes,
            "tipo_selecionado": tipo,
            "sala": sala,
            "cartoes": cartoes,
            "mostrar_vale": mostrar_vale,
            "foco_credito": request.GET.get("pagamento") == "credito",
        },
    )


def _atalhos_do_espaco(request):
    sala = sala_ativa(request)
    if sala:
        return AtalhoLancamento.objects.filter(sala=sala)
    return AtalhoLancamento.objects.filter(proprietario_usuario=request.user)


def _atalho_visivel(request, atalho_id, *, incluir_arquivado=True):
    atalhos = _atalhos_do_espaco(request).select_related("conta_padrao")
    if not incluir_arquivado:
        atalhos = atalhos.filter(arquivado=False)
    return get_object_or_404(atalhos, pk=atalho_id)


def _salvar_atalho(request, atalho=None):
    sala = sala_ativa(request)
    tipo_inicial = atalho.tipo if atalho else request.GET.get(
        "tipo", AtalhoLancamento.Tipo.SAIDA
    )
    if tipo_inicial not in AtalhoLancamento.Tipo.values:
        raise Http404
    mes_consulta, _, _ = mes_ativo(request, request.GET.get("mes"))
    form = AtalhoLancamentoForm(
        request.POST or None,
        instance=atalho,
        tipo=tipo_inicial,
        sala=sala,
        usuario=request.user,
    )
    if request.method == "POST" and form.is_valid():
        novo_atalho = form.save(commit=False)
        novo_atalho.sala = sala
        novo_atalho.proprietario_usuario = None if sala else request.user
        if not novo_atalho.pk:
            maior_ordem = (
                _atalhos_do_espaco(request)
                .filter(tipo=novo_atalho.tipo)
                .aggregate(maior=Max("ordem"))["maior"]
                or 0
            )
            novo_atalho.ordem = maior_ordem + 1
        novo_atalho.full_clean()
        novo_atalho.save()
        messages.success(request, "Item salvo. Nenhum valor foi movimentado.")
        parametros = f"?tipo={novo_atalho.tipo}"
        if mes_consulta:
            parametros += f"&mes={mes_consulta}"
        return redirect(f"{reverse('core:lancamentos')}{parametros}")
    return render(
        request,
        "core/atalho_form.html",
        {
            "form": form,
            "atalho": atalho,
            "opcoes_simbolo": [
                {"id": identificador, **dados}
                for identificador, dados in CATALOGOS_SIMBOLOS[tipo_inicial].items()
            ],
            "tipo_inicial": tipo_inicial,
            "mes_consulta": mes_consulta,
        },
    )


@login_required
def criar_atalho(request):
    return _salvar_atalho(request)


@login_required
def editar_atalho(request, atalho_id):
    return _salvar_atalho(request, _atalho_visivel(request, atalho_id))


@login_required
def gerenciar_atalhos(request):
    return render(
        request,
        "core/atalhos_gerenciar.html",
        {"atalhos": _atalhos_do_espaco(request)},
    )


@login_required
@require_POST
def alternar_arquivo_atalho(request, atalho_id):
    atalho = _atalho_visivel(request, atalho_id)
    atalho.arquivado = not atalho.arquivado
    atalho.save(update_fields=["arquivado", "atualizado_em"])
    acao = "arquivado" if atalho.arquivado else "restaurado"
    messages.success(request, f"Item {acao}. Os lançamentos anteriores foram preservados.")
    if request.POST.get("origem") == "lancamentos":
        tipo = atalho.tipo
        mes = request.POST.get("mes", "")
        parametros = f"?tipo={tipo}"
        if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", mes):
            parametros += f"&mes={mes}"
        return redirect(f"{reverse('core:lancamentos')}{parametros}")
    return redirect("core:gerenciar_atalhos")


@login_required
@require_POST
def mover_atalho(request, atalho_id):
    direcao = request.POST.get("direcao")
    if direcao not in {"subir", "descer"}:
        raise Http404
    with transaction.atomic():
        atalho = get_object_or_404(
            _atalhos_do_espaco(request).select_for_update(),
            pk=atalho_id,
            arquivado=False,
        )
        atalhos = list(
            _atalhos_do_espaco(request)
            .select_for_update()
            .filter(tipo=atalho.tipo, arquivado=False)
            .order_by("ordem", "pk")
        )
        indice = next(i for i, item in enumerate(atalhos) if item.pk == atalho.pk)
        novo_indice = indice - 1 if direcao == "subir" else indice + 1
        if 0 <= novo_indice < len(atalhos):
            vizinho = atalhos[novo_indice]
            atalho.ordem, vizinho.ordem = vizinho.ordem, atalho.ordem
            if atalho.ordem == vizinho.ordem:
                atalho.ordem, vizinho.ordem = novo_indice, indice
            atalho.save(update_fields=["ordem", "atualizado_em"])
            vizinho.save(update_fields=["ordem", "atualizado_em"])
    return redirect("core:gerenciar_atalhos")


def _registro_salvo(request, atalho, tipo):
    identificador = request.GET.get("salvo")
    if not identificador or not identificador.isdigit():
        return None
    sala = sala_ativa(request)
    propriedade = {"sala": sala} if sala else {"proprietario_usuario": request.user}
    modelo = Entrada if tipo == AtalhoLancamento.Tipo.ENTRADA else Saida
    return modelo.objects.filter(pk=identificador, atalho=atalho, **propriedade).first()


@login_required
def registrar_atalho(request, atalho_id):
    atalho = _atalho_visivel(request, atalho_id, incluir_arquivado=False)
    sala = sala_ativa(request)
    controla_dizimos = sala.controlar_dizimos if sala else request.user.dizimo_automatico
    classe_formulario = (
        RegistroRapidoEntradaForm
        if atalho.tipo == AtalhoLancamento.Tipo.ENTRADA
        else RegistroRapidoSaidaForm
    )
    mes_informado = (
        request.POST.get("mes_consulta", "")
        if request.method == "POST"
        else request.GET.get("mes", "")
    )
    mes_consulta, ano, numero_mes = mes_ativo(request, mes_informado)
    form = classe_formulario(
        request.POST or None,
        atalho=atalho,
        sala=sala,
        usuario=request.user,
        data_inicial=data_inicial_do_mes(ano, numero_mes),
        initial={"mes_consulta": mes_consulta},
    )
    if request.method == "POST" and form.is_valid():
        if atalho.tipo == AtalhoLancamento.Tipo.ENTRADA:
            registro, criado = registrar_entrada_por_atalho(
                atalho=atalho,
                sala=sala,
                usuario=request.user,
                dados_formulario=form.cleaned_data,
                controla_dizimos=controla_dizimos,
            )
        else:
            registro, criado = registrar_saida_por_atalho(
                atalho=atalho,
                sala=sala,
                usuario=request.user,
                dados_formulario=form.cleaned_data,
            )
        if criado:
            messages.success(request, f"{atalho.get_tipo_display()} registrada com sucesso.")
        else:
            messages.info(request, "Este formulário já havia sido processado.")
        return redirect(
            f"{reverse('core:lancamentos')}?tipo={atalho.tipo}&mes={mes_consulta}"
        )

    registro_salvo = _registro_salvo(request, atalho, atalho.tipo)
    confirmacao = None
    if registro_salvo:
        if atalho.tipo == AtalhoLancamento.Tipo.ENTRADA:
            data_registro = registro_salvo.data or registro_salvo.data_prevista
            previsto = registro_salvo.situacao == Entrada.Situacao.A_RECEBER
        else:
            data_registro = registro_salvo.data_pagamento or registro_salvo.vencimento
            previsto = registro_salvo.situacao == Saida.Situacao.PENDENTE
        mes_registro = data_registro.strftime("%Y-%m")
        nome_mes = formats.date_format(data_registro, "F \\d\\e Y").capitalize()
        rota_lista = "entradas:lista" if atalho.tipo == "entrada" else "saidas:lista"
        confirmacao = {
            "texto_periodo": (
                f"Previsão registrada para {nome_mes}."
                if previsto
                else f"Registrado em {nome_mes}."
            ),
            "fora_do_periodo": bool(mes_consulta and mes_consulta != mes_registro),
            "url_historico": f"{reverse(rota_lista)}?mes={mes_registro}",
        }

    return render(
        request,
        "core/registro_rapido.html",
        {
            "atalho": atalho,
            "confirmacao": confirmacao,
            "form": form,
            "mes_consulta": mes_consulta,
            "data_mes": data_inicial_do_mes(ano, numero_mes),
        },
    )


@login_required
def registrar_vale(request):
    """Registra o benefício sem criar um item auxiliar no banco."""

    sala = sala_ativa(request)
    controla_dizimos = sala.controlar_dizimos if sala else request.user.dizimo_automatico
    mes_informado = (
        request.POST.get("mes_consulta", "")
        if request.method == "POST"
        else request.GET.get("mes", "")
    )
    mes_consulta, ano, numero_mes = mes_ativo(request, mes_informado)

    form = RegistroRapidoValeForm(
        request.POST or None,
        atalho=None,
        sala=sala,
        usuario=request.user,
        data_inicial=data_inicial_do_mes(ano, numero_mes),
        initial={"mes_consulta": mes_consulta},
    )
    if request.method == "POST" and form.is_valid():
        registro, criado = registrar_vale_rapido(
            sala=sala,
            usuario=request.user,
            dados_formulario=form.cleaned_data,
            controla_dizimos=controla_dizimos,
        )
        if criado:
            messages.success(request, "Vale-alimentação registrado com sucesso.")
        else:
            messages.info(request, "Este formulário já havia sido processado.")
        return redirect(
            f"{reverse('core:lancamentos')}?tipo=entrada&mes={mes_consulta}"
        )

    registro_salvo = None
    identificador = request.GET.get("salvo", "")
    if identificador.isdigit():
        propriedade = {"sala": sala} if sala else {"proprietario_usuario": request.user}
        registro_salvo = Entrada.objects.filter(
            pk=identificador,
            tipo="vale_alimentacao",
            **propriedade,
        ).first()

    confirmacao = None
    if registro_salvo:
        data_registro = registro_salvo.data or registro_salvo.data_prevista
        mes_registro = data_registro.strftime("%Y-%m")
        nome_mes = formats.date_format(data_registro, "F \\d\\e Y").capitalize()
        confirmacao = {
            "texto_periodo": (
                f"Previsão registrada para {nome_mes}."
                if registro_salvo.situacao == Entrada.Situacao.A_RECEBER
                else f"Registrado em {nome_mes}."
            ),
            "fora_do_periodo": bool(mes_consulta and mes_consulta != mes_registro),
            "url_historico": (
                f"{reverse('entradas:lista')}?mes={mes_registro}&tipo=vale_alimentacao"
            ),
        }

    return render(
        request,
        "core/vale_rapido.html",
        {
            "confirmacao": confirmacao,
            "form": form,
            "mes_consulta": mes_consulta,
            "data_mes": data_inicial_do_mes(ano, numero_mes),
        },
    )


def manifesto(request):
    return JsonResponse(
        {
            "name": "Drop Duo",
            "short_name": "Drop Duo",
            "description": "Finanças individuais e compartilhadas de um jeito simples.",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": "#FFF4DC",
            "theme_color": "#2855D9",
            "icons": [
                {
                    "src": "/static/images/app-icon.svg",
                    "sizes": "any",
                    "type": "image/svg+xml",
                    "purpose": "any maskable",
                }
            ],
        },
        content_type="application/manifest+json",
    )


def erro_403(request, exception):
    return render(request, "403.html", status=403)


def erro_404(request, exception):
    return render(request, "404.html", status=404)


def erro_500(request):
    """Mantém a resposta de erro independente do banco e do layout autenticado."""

    return HttpResponse(render_to_string("500.html"), status=500)
