from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from core.espacos import (
    filtrar_no_espaco,
    sala_ativa,
    sala_do_usuario,
    usuario_pode_administrar,
)
from core.periodos import (
    data_inicial_do_mes,
    filtrar_entradas_por_referencia,
    limites_do_mes,
    mes_ativo,
)

from .forms import (
    ConfiguracaoDizimoForm,
    DevolucaoDizimoForm,
    EntradaForm,
    FiltroEntradaForm,
    RecebimentoEntradaForm,
)
from .models import ConfiguracaoDizimo, Entrada
from .services import (
    EntradaErro,
    atualizar_entrada,
    criar_entrada,
    excluir_entrada,
    marcar_entrada_como_recebida,
    registrar_devolucao,
)


def _dizimos_ativos(sala, usuario):
    return sala.controlar_dizimos if sala else usuario.dizimo_automatico


def _entrada_visivel(request, entrada_id):
    return get_object_or_404(
        filtrar_no_espaco(
            Entrada.objects.select_related("pessoa", "conta_destino", "sala"),
            request,
        ),
        pk=entrada_id,
    )


def _dados_configuracoes(sala, usuario):
    if not _dizimos_ativos(sala, usuario):
        return {}
    configuracoes = (
        ConfiguracaoDizimo.objects.filter(sala=sala)
        if sala
        else ConfiguracaoDizimo.objects.filter(proprietario_usuario=usuario)
    )
    return {
        f"{item.pessoa_id}:{item.tipo_entrada}": {
            "calcular": item.calcular_dizimo,
            "forma": item.forma_calculo,
            "percentual": str(item.percentual_dizimo or ""),
            "valorManual": str(item.valor_dizimo_manual or ""),
        }
        for item in configuracoes
    }


def _dados_entrada(form):
    campos = [
        "pessoa", "tipo", "descricao", "valor", "situacao", "data_prevista",
        "data", "conta_destino", "observacao",
        "calcular_dizimo", "forma_calculo", "percentual_dizimo", "valor_dizimo_manual",
    ]
    return {
        campo: form.cleaned_data.get(campo, getattr(form.instance, campo))
        for campo in campos
    }


def _sala_compartilhada(request, form):
    if sala_ativa(request) or not form.cleaned_data.get("compartilhar_sala"):
        return None
    return sala_do_usuario(request.user)


def _parametros_da_lista(request, mes):
    parametros = {"mes": mes}
    for nome in ("pessoa", "tipo", "situacao"):
        if request.GET.get(nome):
            parametros[nome] = request.GET[nome]
    return urlencode(parametros)


def _url_da_lista(request):
    if not request.GET:
        return reverse("entradas:lista")
    mes, _, _ = mes_ativo(request, request.GET.get("mes"))
    return f"{reverse('entradas:lista')}?{_parametros_da_lista(request, mes)}"


@login_required
def lista(request):
    sala = sala_ativa(request)
    mes, ano, numero_mes = mes_ativo(request, request.GET.get("mes"))
    parametros = request.GET.copy()
    parametros["mes"] = mes
    filtro = FiltroEntradaForm(parametros, sala=sala, usuario=request.user)
    entradas = filtrar_no_espaco(
        Entrada.objects.select_related(
            "pessoa", "conta_destino", "proprietario_usuario", "sala", "atalho"
        ).prefetch_related("devolucoes"),
        request,
    )
    inicio, fim = limites_do_mes(ano, numero_mes)
    entradas = filtrar_entradas_por_referencia(entradas, inicio, fim)
    entradas_resumo = entradas.exclude(situacao=Entrada.Situacao.CANCELADA)
    if filtro.is_valid():
        if filtro.cleaned_data.get("pessoa"):
            entradas = entradas.filter(pessoa=filtro.cleaned_data["pessoa"])
            entradas_resumo = entradas_resumo.filter(
                pessoa=filtro.cleaned_data["pessoa"]
            )
        if filtro.cleaned_data.get("tipo"):
            entradas = entradas.filter(tipo=filtro.cleaned_data["tipo"])
        if filtro.cleaned_data.get("situacao"):
            entradas = entradas.filter(situacao=filtro.cleaned_data["situacao"])

    total_entradas_dinheiro = (
        entradas_resumo.exclude(tipo="vale_alimentacao").aggregate(
            total=Sum("valor")
        )["total"]
        or Decimal("0.00")
    )
    total_entradas_vale = (
        entradas_resumo.filter(tipo="vale_alimentacao").aggregate(total=Sum("valor"))["total"]
        or Decimal("0.00")
    )

    parametros_navegacao = _parametros_da_lista(request, mes)
    return render(request, "entradas/lista.html", {
        "sala": sala,
        "titulo_espaco": sala.nome if sala else "Meu espaço",
        "contexto_espaco": sala.nome if sala else "Pessoal",
        "data_mes": inicio,
        "mes_selecionado": mes,
        "parametros_navegacao": parametros_navegacao,
        "voltar_url": f"{reverse('entradas:lista')}?{parametros_navegacao}",
        "entradas": Paginator(entradas, 10).get_page(request.GET.get("page")),
        "filtro": filtro,
        "total_entradas_dinheiro": total_entradas_dinheiro,
        "total_entradas_vale": total_entradas_vale,
        "controla_dizimos": _dizimos_ativos(sala, request.user),
    })


@login_required
def criar(request):
    sala = sala_ativa(request)
    mes, ano, numero_mes = mes_ativo(request, request.GET.get("mes"))
    form = EntradaForm(
        request.POST or None,
        sala=sala,
        usuario=request.user,
        controla_dizimos=_dizimos_ativos(sala, request.user),
        data_inicial=data_inicial_do_mes(ano, numero_mes),
    )
    if request.method == "POST" and form.is_valid():
        entrada, foi_criada = criar_entrada(
            sala=sala,
            proprietario_usuario=None if sala else request.user,
            autor=request.user,
            sala_compartilhada=_sala_compartilhada(request, form),
            chave_idempotencia=form.cleaned_data["chave_formulario"],
            dados=_dados_entrada(form),
        )
        if foi_criada:
            messages.success(request, "Entrada registrada com sucesso.")
        else:
            messages.info(request, "Este formulário já havia sido processado.")
        return redirect(f"{reverse('core:lancamentos')}?tipo=entrada&mes={mes}")

    return render(request, "entradas/formulario.html", {
        "form": form,
        "titulo": "Registrar entrada",
        "texto_botao": "Registrar entrada",
        "data_mes": data_inicial_do_mes(ano, numero_mes),
        "configuracoes_dizimo": _dados_configuracoes(sala, request.user),
        "voltar_url": _url_da_lista(request),
    })


@login_required
def editar(request, entrada_id):
    sala = sala_ativa(request)
    entrada = _entrada_visivel(request, entrada_id)
    if not usuario_pode_administrar(entrada, request.user):
        raise Http404
    if entrada.devolucoes.exists():
        messages.error(request, "Esta entrada possui devoluções vinculadas e não pode ser editada nesta versão.")
        return redirect(_url_da_lista(request))

    form = EntradaForm(
        request.POST or None,
        instance=entrada,
        sala=sala,
        usuario=request.user,
        controla_dizimos=_dizimos_ativos(sala, request.user),
    )
    if request.method == "POST" and form.is_valid():
        dados = _dados_entrada(form)
        if entrada.proprietario_usuario_id and "compartilhar_sala" in form.fields:
            dados["sala_compartilhada"] = _sala_compartilhada(request, form)
        try:
            atualizar_entrada(entrada, dados)
        except EntradaErro as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Entrada atualizada com sucesso.")
        return redirect(_url_da_lista(request))

    return render(request, "entradas/formulario.html", {
        "form": form,
        "titulo": "Editar entrada",
        "texto_botao": "Salvar alterações",
        "configuracoes_dizimo": _dados_configuracoes(sala, request.user),
        "voltar_url": _url_da_lista(request),
    })


@login_required
def excluir(request, entrada_id):
    entrada = _entrada_visivel(request, entrada_id)
    if not usuario_pode_administrar(entrada, request.user):
        raise Http404
    if request.method == "POST":
        try:
            excluir_entrada(entrada)
        except EntradaErro as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Entrada excluída e saldo corrigido.")
        return redirect(_url_da_lista(request))
    return render(request, "entradas/confirmar_exclusao.html", {
        "entrada": entrada,
        "voltar_url": _url_da_lista(request),
    })


@login_required
def devolver(request, entrada_id):
    sala = sala_ativa(request)
    entrada = _entrada_visivel(request, entrada_id)
    if not usuario_pode_administrar(entrada, request.user):
        raise Http404
    if entrada.situacao != Entrada.Situacao.RECEBIDA:
        messages.warning(request, "Confirme o recebimento antes de registrar a devolução.")
        return redirect(_url_da_lista(request))
    if entrada.dizimo_restante <= 0:
        messages.warning(request, "Esta entrada não possui dízimo pendente.")
        return redirect(_url_da_lista(request))

    form = DevolucaoDizimoForm(request.POST or None, sala=sala, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            _, foi_criada = registrar_devolucao(
                entrada=entrada,
                usuario=request.user,
                chave_idempotencia=form.cleaned_data["chave_formulario"],
                dados={campo: form.cleaned_data[campo] for campo in ["valor", "data", "conta"]},
            )
        except EntradaErro as erro:
            form.add_error("valor", str(erro))
        else:
            if foi_criada:
                messages.success(request, "Devolução registrada com sucesso.")
            else:
                messages.info(request, "Este formulário já havia sido processado.")
            return redirect(_url_da_lista(request))
    return render(request, "entradas/devolver.html", {
        "entrada": entrada,
        "form": form,
        "voltar_url": _url_da_lista(request),
    })


@login_required
def receber(request, entrada_id):
    entrada = _entrada_visivel(request, entrada_id)
    if not usuario_pode_administrar(entrada, request.user):
        raise Http404
    if entrada.situacao == Entrada.Situacao.RECEBIDA:
        messages.info(request, "Esta entrada já está recebida.")
        return redirect(_url_da_lista(request))

    form = RecebimentoEntradaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            _, alterada = marcar_entrada_como_recebida(
                entrada, form.cleaned_data["data_recebimento"]
            )
        except EntradaErro as erro:
            form.add_error(None, str(erro))
        else:
            if alterada:
                messages.success(request, "Recebimento confirmado sem duplicar a entrada.")
            return redirect(_url_da_lista(request))
    return render(request, "entradas/receber.html", {
        "entrada": entrada,
        "form": form,
        "voltar_url": _url_da_lista(request),
    })


@login_required
def lista_configuracoes(request):
    sala = sala_ativa(request)
    if not _dizimos_ativos(sala, request.user):
        messages.info(request, "Ative o controle de dízimos nas configurações antes de criar regras.")
        return redirect("entradas:lista")
    configuracoes = (
        ConfiguracaoDizimo.objects.filter(sala=sala)
        if sala
        else ConfiguracaoDizimo.objects.filter(proprietario_usuario=request.user)
    )
    return render(request, "entradas/configuracoes.html", {
        "configuracoes": configuracoes.select_related("pessoa")
    })


def _salvar_configuracao(request, sala, configuracao=None):
    if not _dizimos_ativos(sala, request.user):
        messages.info(request, "Ative o controle de dízimos nas configurações antes de criar regras.")
        return redirect("entradas:lista")
    form = ConfiguracaoDizimoForm(
        request.POST or None,
        instance=configuracao,
        sala=sala,
        usuario=request.user,
    )
    if request.method == "POST" and form.is_valid():
        nova_configuracao = form.save(commit=False)
        nova_configuracao.sala = sala
        nova_configuracao.proprietario_usuario = None if sala else request.user
        nova_configuracao.full_clean()
        nova_configuracao.save()
        messages.success(request, "Configuração de dízimo salva.")
        return redirect("entradas:configuracoes")
    return render(request, "entradas/formulario_configuracao.html", {
        "form": form, "editando": configuracao is not None
    })


@login_required
def criar_configuracao(request):
    return _salvar_configuracao(request, sala_ativa(request))


@login_required
def editar_configuracao(request, configuracao_id):
    sala = sala_ativa(request)
    propriedade = {"sala": sala} if sala else {"proprietario_usuario": request.user}
    configuracao = get_object_or_404(ConfiguracaoDizimo, pk=configuracao_id, **propriedade)
    return _salvar_configuracao(request, sala, configuracao)
