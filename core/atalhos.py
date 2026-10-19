"""Catálogos dos símbolos usados nos itens de entrada e saída."""


_DADOS_SIMBOLOS_ENTRADA = [
    ("salario", "Salário", "01_salario.png"),
    ("bonus", "Bônus", "02_bonus.png"),
    ("segundo_emprego", "Segundo emprego", "03_segundo_emprego.png"),
    ("investimento", "Investimento", "04_investimento.png"),
    ("renda_extra", "Renda extra", "05_renda_extra.png"),
    ("ferias", "Férias", "06_ferias.png"),
    ("decimo_terceiro", "Décimo terceiro", "07_decimo_terceiro.png"),
]

_DADOS_SIMBOLOS_SAIDA = [
    ("supermercado", "Supermercado", "01_supermercado.png"),
    ("restaurante", "Restaurante", "02_restaurante.png"),
    ("fastfood", "Fast-food", "03_fastfood.png"),
    ("cafeteria", "Cafeteria", "04_cafeteria.png"),
    ("bebidas", "Bebidas", "05_bebidas.png"),
    ("casa", "Casa", "06_casa.png"),
    ("energia", "Energia", "07_energia.png"),
    ("agua", "Água", "08_agua.png"),
    ("internet", "Internet", "09_internet.png"),
    ("celular", "Celular", "10_celular.png"),
    ("manutencao", "Manutenção", "11_manutencao.png"),
    ("limpeza", "Limpeza", "12_limpeza.png"),
    ("combustivel", "Combustível", "13_combustivel.png"),
    ("carro", "Carro", "14_carro.png"),
    ("taxi", "Táxi", "15_taxi.png"),
    ("onibus", "Ônibus", "16_onibus.png"),
    ("trem", "Trem", "17_trem.png"),
    ("estacionamento", "Estacionamento", "18_estacionamento.png"),
    ("moto", "Moto", "19_moto.png"),
    ("farmacia", "Farmácia", "20_farmacia.png"),
    ("hospital", "Hospital", "21_hospital.png"),
    ("dentista", "Dentista", "22_dentista.png"),
    ("otica", "Ótica", "23_otica.png"),
    ("academia", "Academia", "24_academia.png"),
    ("salao", "Salão", "25_salao.png"),
    ("cosmeticos", "Cosméticos", "26_cosmeticos.png"),
    ("escola", "Escola", "27_escola.png"),
    ("estudos", "Estudos", "28_estudos.png"),
    ("papelaria", "Papelaria", "29_papelaria.png"),
    ("trabalho", "Trabalho", "30_trabalho.png"),
    ("viagem", "Viagem", "31_viagem.png"),
    ("streaming", "Streaming", "32_streaming.png"),
    ("games", "Games", "33_games.png"),
    ("festas", "Festas", "34_festas.png"),
    ("shopping", "Shopping", "35_shopping.png"),
    ("roupas", "Roupas", "36_roupas.png"),
    ("calcados", "Calçados", "37_calcados.png"),
    ("eletronicos", "Eletrônicos", "38_eletronicos.png"),
    ("presentes", "Presentes", "39_presentes.png"),
    ("bebe", "Bebê", "40_bebe.png"),
    ("crianca", "Criança", "41_crianca.png"),
    ("pet", "Pet", "42_pet.png"),
    ("seguros", "Seguros", "43_seguros.png"),
    ("banco", "Banco", "44_banco.png"),
    ("financas", "Finanças", "45_financas.png"),
    ("poupanca", "Poupança", "46_poupanca.png"),
    ("impostos", "Impostos", "47_impostos.png"),
    ("investimentos", "Investimentos", "48_investimentos.png"),
    ("camisa", "Camisa", "49_camisa.png"),
    ("vestido", "Vestido", "50_vestido.png"),
    ("salto", "Salto", "51_salto.png"),
    ("joias", "Joias", "52_joias.png"),
    ("fotografia", "Fotografia", "53_fotografia.png"),
    ("hobbies", "Hobbies", "54_hobbies.png"),
]


def _montar_catalogo(tipo, dados):
    return {
        f"{tipo}_{identificador}": {
            "nome": nome,
            "arquivo": f"dropduo/item-icons/{tipo}/{arquivo}",
            "tipo": tipo,
        }
        for identificador, nome, arquivo in dados
    }


CATALOGOS_SIMBOLOS = {
    "entrada": _montar_catalogo("entrada", _DADOS_SIMBOLOS_ENTRADA),
    "saida": _montar_catalogo("saida", _DADOS_SIMBOLOS_SAIDA),
}
SIMBOLOS_ATALHO = {
    identificador: dados
    for catalogo in CATALOGOS_SIMBOLOS.values()
    for identificador, dados in catalogo.items()
}
SIMBOLOS_PADRAO_POR_TIPO = {
    "entrada": "entrada_renda_extra",
    "saida": "saida_financas",
}
# Mantido como atalho para os pontos antigos que sempre criam uma saída.
SIMBOLO_PADRAO = SIMBOLOS_PADRAO_POR_TIPO["saida"]

# Estes caminhos existem apenas para exibir um registro legado antes da migração.
# Eles não são oferecidos no cadastro ou na edição de itens.
SIMBOLOS_LEGADOS = {
    identificador: {"arquivo": f"dropduo/item-icons/{arquivo}"}
    for identificador, _, arquivo in _DADOS_SIMBOLOS_SAIDA
}

CATEGORIAS_ENTRADA = [
    ("salario", "Salário"),
    ("extra", "Extra"),
    ("segundo_emprego", "Segundo emprego"),
    ("fgts", "FGTS"),
    ("decimo_terceiro", "Décimo terceiro"),
    ("vale_alimentacao", "Vale-alimentação"),
    ("outros", "Outros"),
]
CATEGORIAS_SAIDA = [
    ("moradia", "Moradia"),
    ("alimentacao", "Alimentação"),
    ("transporte", "Transporte"),
    ("educacao", "Educação"),
    ("saude", "Saúde"),
    ("lazer", "Lazer"),
    ("outros", "Outros"),
]

CATEGORIAS_CUSTO_VIDA = {"moradia", "alimentacao", "transporte", "educacao", "saude"}

_SIMBOLOS_POR_CATEGORIA_SAIDA = {
    "alimentacao": {"supermercado", "restaurante", "fastfood", "cafeteria", "bebidas"},
    "moradia": {"casa", "energia", "agua", "internet", "celular", "manutencao", "limpeza", "seguros", "impostos"},
    "transporte": {"combustivel", "carro", "taxi", "onibus", "trem", "estacionamento", "moto"},
    "saude": {"farmacia", "hospital", "dentista", "otica", "academia"},
    "educacao": {"escola", "estudos", "papelaria"},
    "lazer": {"viagem", "streaming", "games", "festas", "fotografia", "hobbies"},
}


def categorias_do_tipo(tipo):
    return CATEGORIAS_ENTRADA if tipo == "entrada" else CATEGORIAS_SAIDA


def simbolos_do_tipo(tipo):
    """Retorna somente os símbolos permitidos para o tipo informado."""

    return CATALOGOS_SIMBOLOS.get(tipo, {})


def simbolo_pertence_ao_tipo(simbolo, tipo):
    return simbolo in simbolos_do_tipo(tipo)


def caminho_do_simbolo(simbolo, tipo):
    """Resolve o arquivo novo e mantém uma exibição segura para dados legados."""

    dados = SIMBOLOS_ATALHO.get(simbolo) or SIMBOLOS_LEGADOS.get(simbolo)
    if dados:
        return dados["arquivo"]
    simbolo_padrao = SIMBOLOS_PADRAO_POR_TIPO.get(tipo, SIMBOLO_PADRAO)
    return SIMBOLOS_ATALHO[simbolo_padrao]["arquivo"]


def categoria_padrao_do_item(tipo, simbolo):
    """Escolhe uma categoria simples a partir do tipo e do símbolo do item."""

    nome_simbolo = simbolo.removeprefix(f"{tipo}_")
    if tipo == "entrada":
        categorias_por_simbolo = {
            "salario": "salario",
            "bonus": "extra",
            "segundo_emprego": "segundo_emprego",
            "renda_extra": "extra",
            "decimo_terceiro": "decimo_terceiro",
        }
        return categorias_por_simbolo.get(nome_simbolo, "outros")
    for categoria, simbolos in _SIMBOLOS_POR_CATEGORIA_SAIDA.items():
        if nome_simbolo in simbolos:
            return categoria
    return "outros"
