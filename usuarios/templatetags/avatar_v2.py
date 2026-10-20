import json

from django import template
from django.templatetags.static import static

from usuarios.avatar_catalogo import CORES_CABELO, CORES_ROUPA, TONS_PELE


register = template.Library()

PASTA_AVATAR = "dropduo/avatars/v2/pieces"


def _arquivos_do_avatar():
    """Lista cada asset usado pelo compositor para o storage gerar sua URL real."""

    arquivos = {
        "baseM": "base-m.png",
        "baseF": "base-f.png",
        "jacketBaseM": "base-m-jacket.png",
        "jacketBaseF": "base-f-jacket.png",
        "jacket": "jacket.png",
    }
    for base in ("m", "f"):
        for tom in TONS_PELE:
            nome = f"skin/base-{base}-{tom}.png"
            arquivos[nome] = f"rendered/{nome}"
        for cor in CORES_ROUPA:
            nome = f"shirt/base-{base}-{cor}.png"
            arquivos[nome] = f"rendered/{nome}"
    for tipo in ("beard-short", "hair-short", "hair-long"):
        for cor in CORES_CABELO:
            nome = f"hair/{tipo}-{cor}.png"
            arquivos[nome] = f"rendered/{nome}"
    return arquivos


@register.simple_tag
def avatar_v2_asset_urls():
    """Entrega ao JavaScript URLs processadas pelo static storage do Django."""

    urls = {
        identificador: static(f"{PASTA_AVATAR}/{arquivo}")
        for identificador, arquivo in _arquivos_do_avatar().items()
    }
    return json.dumps(urls, separators=(",", ":"))
