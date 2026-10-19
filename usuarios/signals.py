from allauth.socialaccount.signals import (
    social_account_added,
    social_account_updated,
)
from django.dispatch import receiver


def sincronizar_dados_google(sociallogin):
    """Copia dados públicos do perfil Google para o usuário local."""
    if sociallogin.account.provider != "google":
        return

    usuario = sociallogin.user
    dados_google = sociallogin.account.extra_data
    campos_atualizados = []

    campos_google = {
        "first_name": "given_name",
        "last_name": "family_name",
        "email": "email",
        "foto_url": "picture",
    }

    for campo_usuario, campo_google in campos_google.items():
        novo_valor = dados_google.get(campo_google)
        if novo_valor and getattr(usuario, campo_usuario) != novo_valor:
            setattr(usuario, campo_usuario, novo_valor)
            campos_atualizados.append(campo_usuario)

    if campos_atualizados:
        usuario.save(update_fields=campos_atualizados)


@receiver(social_account_added)
@receiver(social_account_updated)
def atualizar_usuario_com_google(sender, request, sociallogin, **kwargs):
    sincronizar_dados_google(sociallogin)
