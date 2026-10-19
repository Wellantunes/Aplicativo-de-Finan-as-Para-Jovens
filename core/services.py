from django.db import transaction
from django.utils import timezone

from entradas.models import ConfiguracaoDizimo, Entrada, TipoEntrada
from entradas.services import criar_entrada
from saidas.models import Saida
from saidas.services import criar_saida

from .atalhos import CATEGORIAS_CUSTO_VIDA
from .espacos import sala_para_novo_compartilhamento


def _configuracao_dizimo(sala, usuario, tipo_entrada, controla_dizimos):
    if not controla_dizimos:
        return None
    filtros = {"sala": sala} if sala else {"proprietario_usuario": usuario}
    return ConfiguracaoDizimo.objects.filter(
        pessoa=usuario,
        tipo_entrada=tipo_entrada,
        **filtros,
    ).first()


@transaction.atomic
def registrar_entrada_por_atalho(
    *, atalho, sala, usuario, dados_formulario, controla_dizimos
):
    configuracao = _configuracao_dizimo(
        sala,
        usuario,
        atalho.categoria,
        controla_dizimos,
    )
    calcular_dizimo = bool(configuracao and configuracao.calcular_dizimo)
    recebida = dados_formulario["situacao"] == Entrada.Situacao.RECEBIDA
    dados = {
        "pessoa": usuario,
        "tipo": atalho.categoria,
        "descricao": atalho.nome,
        "valor": dados_formulario["valor"],
        "situacao": dados_formulario["situacao"],
        "data_prevista": dados_formulario["data"],
        "data": dados_formulario["data"] if recebida else None,
        "conta_destino": None,
        "observacao": dados_formulario.get("observacao", ""),
        "atalho": atalho,
        "categoria_atalho": atalho.categoria,
        "calcular_dizimo": calcular_dizimo,
        "forma_calculo": configuracao.forma_calculo if calcular_dizimo else "",
        "percentual_dizimo": (
            configuracao.percentual_dizimo if calcular_dizimo else None
        ),
        "valor_dizimo_manual": (
            configuracao.valor_dizimo_manual if calcular_dizimo else None
        ),
    }
    sala_compartilhada = (
        None if sala else sala_para_novo_compartilhamento(usuario)
    )
    return criar_entrada(
        sala=sala,
        proprietario_usuario=None if sala else usuario,
        autor=usuario,
        sala_compartilhada=sala_compartilhada,
        chave_idempotencia=dados_formulario["chave_formulario"],
        dados=dados,
    )


@transaction.atomic
def registrar_vale_rapido(*, sala, usuario, dados_formulario, controla_dizimos):
    configuracao = _configuracao_dizimo(
        sala,
        usuario,
        TipoEntrada.VALE_ALIMENTACAO,
        controla_dizimos,
    )
    calcular_dizimo = bool(configuracao and configuracao.calcular_dizimo)
    data = dados_formulario["data"]
    recebida = data <= timezone.localdate()
    situacao = Entrada.Situacao.RECEBIDA if recebida else Entrada.Situacao.A_RECEBER
    dados = {
        "pessoa": usuario,
        "tipo": TipoEntrada.VALE_ALIMENTACAO,
        "descricao": dados_formulario["descricao"],
        "valor": dados_formulario["valor"],
        "situacao": situacao,
        "data_prevista": data,
        "data": data if recebida else None,
        "conta_destino": None,
        "observacao": "",
        "atalho": None,
        "categoria_atalho": TipoEntrada.VALE_ALIMENTACAO,
        "calcular_dizimo": calcular_dizimo,
        "forma_calculo": configuracao.forma_calculo if calcular_dizimo else "",
        "percentual_dizimo": configuracao.percentual_dizimo if calcular_dizimo else None,
        "valor_dizimo_manual": configuracao.valor_dizimo_manual if calcular_dizimo else None,
    }
    sala_compartilhada = None if sala else sala_para_novo_compartilhamento(usuario)
    return criar_entrada(
        sala=sala,
        proprietario_usuario=None if sala else usuario,
        autor=usuario,
        sala_compartilhada=sala_compartilhada,
        chave_idempotencia=dados_formulario["chave_formulario"],
        dados=dados,
    )


@transaction.atomic
def registrar_saida_por_atalho(*, atalho, sala, usuario, dados_formulario):
    paga = dados_formulario["situacao"] == Saida.Situacao.PAGA
    dados = {
        "descricao": atalho.nome,
        "valor": dados_formulario["valor"],
        "responsavel": usuario,
        "custo_vida": atalho.categoria in CATEGORIAS_CUSTO_VIDA,
        "situacao": dados_formulario["situacao"],
        "vencimento": dados_formulario["data"],
        "data_pagamento": dados_formulario["data"] if paga else None,
        "forma_pagamento": "",
        "conta": None,
        "observacao": dados_formulario.get("observacao", ""),
        "atalho": atalho,
        "categoria_atalho": atalho.categoria,
    }
    sala_compartilhada = (
        None if sala else sala_para_novo_compartilhamento(usuario)
    )
    return criar_saida(
        sala=sala,
        proprietario_usuario=None if sala else usuario,
        autor=usuario,
        sala_compartilhada=sala_compartilhada,
        chave_idempotencia=dados_formulario["chave_formulario"],
        dados=dados,
    )
