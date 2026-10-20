import html
import json
import re
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse


class AvatarStaticStorageTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="avatar_manifest",
            avatar_concluido=True,
            avatar_versao=2,
            configuracao_inicial_concluida=True,
        )
        self.client.force_login(self.usuario)

    def test_avatar_usa_urls_do_manifest_sem_concatenar_diretorio(self):
        storages = {
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {
                "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
            },
        }
        with tempfile.TemporaryDirectory() as pasta_estatica:
            with override_settings(STATIC_ROOT=pasta_estatica, STORAGES=storages):
                call_command("collectstatic", interactive=False, verbosity=0)
                response = self.client.get(reverse("usuarios:perfil"))

            conteudo = response.content.decode()
            correspondencia = re.search(r'data-avatar-assets="([^"]+)"', conteudo)
            self.assertIsNotNone(correspondencia)
            assets = json.loads(html.unescape(correspondencia.group(1)))

            self.assertNotIn("data-asset-rendered-root", conteudo)
            self.assertIn("skin/base-m-media.png", assets)
            self.assertIn("hair/hair-long-castanho.png", assets)
            self.assertRegex(assets["baseM"], r"base-m\.[0-9a-f]{12}\.png$")
            for url in assets.values():
                caminho_relativo = url.removeprefix("/static/")
                self.assertTrue(Path(pasta_estatica, caminho_relativo).is_file(), url)
