import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import get_messages
from django.contrib.messages.storage.base import Message
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import HttpResponse
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import reverse

from usuarios.adapters import AccountAdapter
from .views import erro_403, erro_404, erro_500
from .logging import OcultarDadosSensiveisFilter


class PaginasDeErroTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/rota-inexistente/")
        self.request.user = AnonymousUser()

    def test_paginas_de_erro_sao_independentes_do_layout_autenticado(self):
        respostas = [
            erro_403(self.request, PermissionError()),
            erro_404(self.request, LookupError()),
            erro_500(self.request),
        ]

        self.assertEqual([resposta.status_code for resposta in respostas], [403, 404, 500])
        for resposta in respostas:
            conteudo = resposta.content.decode("utf-8")
            self.assertIn("Drop Duo", conteudo)
            self.assertNotIn("bottom-navigation", conteudo)


class FiltroDeLogsTests(TestCase):
    def test_oculta_codigo_de_convite_e_parametros_da_url(self):
        registro = logging.LogRecord(
            name="django.request",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="Erro em %s",
            args=("/salas/convites/ABC12345/confirmar/?code=segredo",),
            exc_info=None,
        )

        OcultarDadosSensiveisFilter().filter(registro)
        mensagem = registro.getMessage()

        self.assertNotIn("ABC12345", mensagem)
        self.assertNotIn("segredo", mensagem)
        self.assertIn("[codigo-oculto]", mensagem)
        self.assertIn("[parametros-ocultos]", mensagem)


class HomeViewTests(TestCase):
    def test_home_page_is_available(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "auth/entrar.html")

    def test_home_page_has_mobile_viewport_and_presentation(self):
        response = self.client.get(reverse("core:home"))

        self.assertContains(response, 'name="viewport"')
        self.assertContains(response, "Seu dinheiro. Sua próxima fase.")
        self.assertContains(response, "Entre no seu espaço")
        self.assertContains(response, "Continuar com Google")
        self.assertContains(response, "auth.css")

    def test_login_publico_oferece_somente_google(self):
        response = self.client.get(reverse("core:entrar"))

        self.assertContains(response, "Continuar com Google")
        self.assertContains(response, "exclusivamente pelo Google")
        self.assertNotContains(response, 'type="email"')
        self.assertNotContains(response, 'type="password"')

    def test_criar_conta_publica_usa_somente_google(self):
        response = self.client.get(reverse("core:criar_conta"))

        self.assertContains(response, "Comece sua próxima fase")
        self.assertContains(response, "Continuar com Google")
        self.assertNotContains(response, 'type="email"')
        self.assertNotContains(response, 'type="password"')
        self.assertEqual(self.client.post(reverse("core:criar_conta")).status_code, 405)

    def test_pagina_de_ajuda_nao_oferece_recuperacao_por_senha(self):
        response = self.client.get(reverse("core:recuperar_senha"))

        self.assertContains(response, "Recuperar acesso")
        self.assertContains(response, "Continuar com Google")
        self.assertNotContains(response, 'type="email"')
        self.assertNotContains(response, 'type="password"')
        self.assertEqual(
            self.client.post(reverse("core:recuperar_senha")).status_code,
            405,
        )

    def test_new_authenticated_user_starts_quick_setup(self):
        usuario = get_user_model().objects.create_user(
            username="maria",
            first_name="Maria",
            email="maria@example.com",
            foto_url="https://example.com/maria.jpg",
        )
        self.client.force_login(usuario)

        response = self.client.get(reverse("core:home"))

        self.assertRedirects(response, reverse("usuarios:avatar"))

    def test_user_with_room_is_redirected_to_dashboard(self):
        from salas.models import MembroSala, Sala

        usuario = get_user_model().objects.create_user(
            username="com_sala",
            configuracao_inicial_concluida=True,
            avatar_concluido=True,
        )
        sala = Sala.objects.create(
            nome="Nossa casa",
            orcamento_mensal="2500.00",
            criado_por=usuario,
        )
        MembroSala.objects.create(sala=sala, usuario=usuario)
        self.client.force_login(usuario)

        response = self.client.get(reverse("core:home"))

        self.assertRedirects(response, reverse("dashboard:mensal"))
        self.assertEqual(self.client.session["espaco_financeiro"], "individual")

    def test_logout_ends_user_session(self):
        usuario = get_user_model().objects.create_user(username="usuario_logado")
        self.client.force_login(usuario)

        response = self.client.post(reverse("account_logout"))

        self.assertRedirects(response, reverse("core:home"))
        self.assertNotIn("_auth_user_id", self.client.session)


class AuthenticationLibraryTests(TestCase):
    def test_confirmacao_de_login_recebe_tag_especifica(self):
        request = RequestFactory().get("/")
        SessionMiddleware(lambda current_request: None).process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)

        AccountAdapter().add_message(
            request,
            messages.SUCCESS,
            "account/messages/logged_in.txt",
            {"user": get_user_model()(username="maria")},
        )
        messages.error(request, "Erro importante")
        mensagens = list(get_messages(request))

        self.assertIn("login-success", mensagens[0].tags)
        self.assertNotIn("login-success", mensagens[1].tags)

    def test_allauth_routes_are_available(self):
        self.assertEqual(reverse("account_login"), "/accounts/login/")
        self.assertEqual(reverse("google_login"), "/accounts/google/login/")
        self.assertEqual(
            reverse("google_callback"),
            "/accounts/google/login/callback/",
        )

    def test_fluxos_de_senha_do_allauth_estao_desativados(self):
        self.assertEqual(self.client.get("/accounts/signup/").status_code, 404)
        self.assertEqual(self.client.get("/accounts/password/reset/").status_code, 404)

    def test_login_administrativo_continua_disponivel(self):
        self.assertEqual(self.client.get("/admin/login/").status_code, 200)

    def test_google_provider_uses_environment_credentials(self):
        google_app = settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]

        self.assertTrue(bool(google_app["client_id"]))
        self.assertTrue(bool(google_app["secret"]))

    def test_google_login_start_page_is_available(self):
        response = self.client.get(reverse("google_login"))

        self.assertEqual(response.status_code, 200)

    def test_login_do_allauth_usa_layout_publico_do_drop_duo(self):
        response = self.client.get(reverse("account_login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "account/login.html")
        self.assertContains(response, "Entre no seu espaço")
        self.assertContains(response, "auth.css")
        self.assertNotContains(response, 'aria-label="Navegação principal"')

    def test_google_login_redirects_to_google(self):
        response = self.client.post(reverse("google_login"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts.google.com", response.url)


class MessageFeedbackTests(TestCase):
    def _store_messages(self, *stored_messages):
        request = RequestFactory().get("/")
        SessionMiddleware(lambda current_request: None).process_request(request)
        request.session.save()
        storage = FallbackStorage(request)
        for stored_message in stored_messages:
            storage.add(
                stored_message.level,
                stored_message.message,
                stored_message.extra_tags,
            )
        response = HttpResponse()
        storage.update(response)
        self.client.cookies.update(response.cookies)

    def test_public_layout_only_auto_dismisses_success_and_information(self):
        self._store_messages(
            Message(messages.SUCCESS, "Operação concluída"),
            Message(messages.INFO, "Informação temporária"),
            Message(messages.WARNING, "Aviso importante"),
            Message(messages.ERROR, "Erro de validação"),
        )

        response = self.client.get(reverse("core:home"))

        self.assertContains(response, "data-dismissible-message", count=4)
        self.assertContains(response, "data-dismiss-message", count=4)
        self.assertContains(response, 'aria-label="Dispensar aviso"', count=4)
        self.assertContains(response, "data-auto-dismiss-message", count=2)
        self.assertContains(response, 'role="alert"', count=1)

    def test_authenticated_layout_uses_the_same_message_lifecycle(self):
        user = get_user_model().objects.create_user(
            username="feedback",
            avatar_concluido=True,
            configuracao_inicial_concluida=True,
        )
        self.client.force_login(user)
        self._store_messages(
            Message(messages.SUCCESS, "Item salvo"),
            Message(messages.ERROR, "Revise os dados"),
        )

        response = self.client.get(reverse("core:lancamentos"))

        self.assertContains(response, "data-dismissible-message", count=2)
        self.assertContains(response, "data-dismiss-message", count=2)
        self.assertContains(response, 'aria-label="Dispensar aviso"', count=2)
        self.assertContains(response, "data-auto-dismiss-message", count=1)

    def test_rendered_messages_are_consumed_after_the_first_response(self):
        self._store_messages(Message(messages.SUCCESS, "Mensagem de uma exibição"))

        first_response = self.client.get(reverse("core:home"))
        second_response = self.client.get(reverse("core:home"))

        self.assertContains(first_response, "Mensagem de uma exibição")
        self.assertNotContains(second_response, "Mensagem de uma exibição")


class MobileExperienceTests(TestCase):
    def setUp(self):
        from salas.models import MembroSala, Sala

        self.usuario = get_user_model().objects.create_user(
            username="mobile",
            configuracao_inicial_concluida=True,
            avatar_concluido=True,
        )
        self.sala = Sala.objects.create(
            nome="Casa mobile",
            orcamento_mensal="1500.00",
            controlar_dizimos=True,
            criado_por=self.usuario,
        )
        MembroSala.objects.create(sala=self.sala, usuario=self.usuario)
        sessao = self.client.session
        sessao["espaco_financeiro"] = "sala"
        sessao.save()

    def test_manifesto_tem_configuracao_instalavel_sem_cache_offline(self):
        response = self.client.get(reverse("core:manifesto"))
        manifesto = response.json()

        self.assertEqual(response["Content-Type"], "application/manifest+json")
        self.assertEqual(manifesto["display"], "standalone")
        self.assertEqual(manifesto["start_url"], "/")
        self.assertTrue(manifesto["icons"])
        self.assertNotIn("serviceworker", manifesto)

    def test_usuario_com_sala_ve_navegacao_e_registro_rapido(self):
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("dashboard:mensal"), {"mes": "2026-10"})

        self.assertContains(response, 'aria-label="Navegação principal"')
        self.assertContains(response, reverse("core:lancamentos"))
        self.assertContains(response, reverse("cartoes:lista"))
        self.assertNotContains(response, f'href="{reverse("contas:lista")}"')
        self.assertContains(response, reverse("salas:minha_sala"))
        self.assertContains(response, "Adicionar")
        self.assertContains(response, "Ocultar valores")
        destino_saida = reverse("core:lancamentos") + "?tipo=saida&amp;mes=2026-10"
        destino_entrada = reverse("core:lancamentos") + "?tipo=entrada&amp;mes=2026-10"
        self.assertContains(response, f'href="{destino_saida}"')
        self.assertContains(response, f'href="{destino_entrada}"')
        self.assertNotContains(response, f'href="{reverse("entradas:criar")}"')
        self.assertNotContains(response, f'href="{reverse("saidas:criar")}"')

    def test_paginas_autenticadas_nao_sao_armazenadas_em_cache(self):
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("dashboard:mensal"))

        cache_control = response["Cache-Control"]
        self.assertIn("no-store", cache_control)
        self.assertIn("private", cache_control)

    def test_central_de_lancamentos_exige_sessao_ativa(self):
        response = self.client.get(reverse("core:lancamentos"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("account_login"), response.url)

    def test_central_de_lancamentos_mostra_fluxo_simplificado(self):
        self.client.force_login(self.usuario)

        response = self.client.get(reverse("core:lancamentos"))

        self.assertContains(response, "Saída")
        self.assertContains(response, "Entrada")
        self.assertContains(response, "Novo item")
        self.assertNotContains(response, "Organizar itens")
        self.assertNotContains(response, "Lançamento avulso")
        self.assertNotContains(response, "Histórico")
