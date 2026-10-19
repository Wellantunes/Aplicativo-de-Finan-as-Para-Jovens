import logging
import re


CODIGO_CONVITE_NA_URL = re.compile(r"(/salas/convites/)[^/?]+")


def _ocultar_dados_da_url(valor):
    if not isinstance(valor, str):
        return valor
    valor = CODIGO_CONVITE_NA_URL.sub(r"\1[codigo-oculto]", valor)
    if "?" in valor:
        valor = f"{valor.split('?', 1)[0]}?[parametros-ocultos]"
    return valor


class OcultarDadosSensiveisFilter(logging.Filter):
    """Evita que códigos e parâmetros de URL sejam gravados nos logs."""

    def filter(self, record):
        record.msg = _ocultar_dados_da_url(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_ocultar_dados_da_url(item) for item in record.args)
        elif isinstance(record.args, dict):
            record.args = {
                chave: _ocultar_dados_da_url(valor)
                for chave, valor in record.args.items()
            }
        return True
