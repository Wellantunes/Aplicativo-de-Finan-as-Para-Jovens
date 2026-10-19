"""Opções permitidas para o avatar visual da versão 2."""

VERSAO_AVATAR_ATUAL = 2

BASES = {
    "masculina": "Masculina",
    "feminina": "Feminina",
}

TONS_PELE = {
    "muito_clara": {"nome": "Muito clara", "cor": "#f4cea8"},
    "clara": {"nome": "Clara", "cor": "#e9ad76"},
    "media": {"nome": "Média", "cor": "#d88b52"},
    "morena": {"nome": "Morena", "cor": "#b97443"},
    "escura": {"nome": "Escura", "cor": "#8c502f"},
    "muito_escura": {"nome": "Muito escura", "cor": "#583526"},
}

CABELOS = {
    "sem_cabelo": "Sem cabelo",
    "curto": "Curto",
    "comprido": "Comprido",
}

CORES_CABELO = {
    "preto": {"nome": "Preto", "cor": "#241d1c"},
    "castanho": {"nome": "Castanho", "cor": "#58351f"},
    "castanho_claro": {"nome": "Castanho claro", "cor": "#95613b"},
    "loiro": {"nome": "Loiro", "cor": "#d4ad61"},
    "ruivo": {"nome": "Ruivo", "cor": "#a7442c"},
    "grisalho": {"nome": "Grisalho", "cor": "#b8b5ae"},
}

BARBAS = {
    "sem_barba": "Sem barba",
    "curta": "Barba curta",
}

ROUPAS = {
    "camiseta": "Camiseta",
    "camisa_azul": "Camisa azul",
}

CORES_ROUPA = {
    "creme": {"nome": "Creme", "cor": "#eee5cd"},
    "coral": {"nome": "Coral", "cor": "#ed7057"},
    "azul": {"nome": "Azul", "cor": "#2456c9"},
    "verde": {"nome": "Verde", "cor": "#487d64"},
    "roxo": {"nome": "Roxo", "cor": "#674981"},
    "grafite": {"nome": "Grafite", "cor": "#333744"},
}


def escolhas(opcoes):
    return [
        (identificador, dados["nome"] if isinstance(dados, dict) else dados)
        for identificador, dados in opcoes.items()
    ]


BASE_CHOICES = escolhas(BASES)
PELE_CHOICES = escolhas(TONS_PELE)
CABELO_CHOICES = escolhas(CABELOS)
COR_CABELO_CHOICES = escolhas(CORES_CABELO)
BARBA_CHOICES = escolhas(BARBAS)
ROUPA_CHOICES = escolhas(ROUPAS)
COR_ROUPA_CHOICES = escolhas(CORES_ROUPA)

