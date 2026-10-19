from types import SimpleNamespace
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from contas.models import Conta
from entradas.models import Entrada, TipoEntrada
from saidas.models import Saida
from salas.models import MembroSala, Sala

from .signals import sincronizar_dados_google


class UsuarioModelTests(TestCase):
    def test_uses_custom_user_model(self):
        self.assertEqual(get_user_model()._meta.label, "usuarios.Usuario")

    def test_user_can_authenticate_with_allauth_backend(self):
        get_user_model().objects.create_user(
            username="usuario_teste",
            password="senha-segura-123",
        )

        authenticated = self.client.login(
            username="usuario_teste",
            password="senha-segura-123",
        )

        self.assertTrue(authenticated)

    def test_syncs_google_profile_data(self):
        usuario = get_user_model().objects.create_user(username="perfil_google")
        sociallogin = SimpleNamespace(
            user=usuario,
            account=SimpleNamespace(
                provider="google",
                extra_data={
                    "given_name": "Ana",
                    "family_name": "Silva",
                    "email": "ana@example.com",
                    "picture": "https://example.com/ana.jpg",
                },
            ),
        )

        sincronizar_dados_google(sociallogin)
        usuario.refresh_from_db()

        self.assertEqual(usuario.first_name, "Ana")
        self.assertEqual(usuario.last_name, "Silva")
        self.assertEqual(usuario.email, "ana@example.com")
        self.assertEqual(usuario.foto_url, "https://example.com/ana.jpg")


class PreferenciasEConsentimentoTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="preferencias",
            configuracao_inicial_concluida=True,
        )
        self.sala = Sala.objects.create(
            nome="Nossa casa",
            orcamento_mensal=Decimal("1000.00"),
            criado_por=self.usuario,
        )
        MembroSala.objects.create(sala=self.sala, usuario=self.usuario)
        self.conta = Conta.objects.create(
            proprietario_usuario=self.usuario,
            autor=self.usuario,
            titular=self.usuario,
            tipo=Conta.Tipo.DINHEIRO,
            nome="Conta pessoal",
            saldo_inicial=Decimal("100.00"),
            data_saldo_inicial=date(2026, 1, 1),
        )
        self.entrada = Entrada.objects.create(
            proprietario_usuario=self.usuario,
            autor=self.usuario,
            pessoa=self.usuario,
            tipo=TipoEntrada.SALARIO,
            descricao="Entrada antiga",
            valor=Decimal("500.00"),
            data=date(2026, 9, 1),
            conta_destino=self.conta,
            calcular_dizimo=True,
            forma_calculo="percentual",
            percentual_dizimo=Decimal("10.00"),
            dizimo_previsto=Decimal("50.00"),
        )
        self.client.force_login(self.usuario)

    def test_alterar_percentual_padrao_nao_recalcula_historico(self):
        response = self.client.post(reverse("usuarios:perfil"), {
            "renda_mensal_prevista": "3000.00",
            "orcamento_mensal_individual": "900.00",
            "dizimo_automatico": "on",
            "percentual_dizimo_padrao": "20.00",
        })
        self.assertRedirects(response, reverse("usuarios:perfil"))
        self.entrada.refresh_from_db()
        self.assertEqual(self.entrada.dizimo_previsto, Decimal("50.00"))

    def test_perfil_mostra_contas_antigas_somente_quando_existirem(self):
        response = self.client.get(reverse("usuarios:perfil"))

        self.assertContains(response, "Consultar contas antigas")
        self.assertContains(response, reverse("contas:lista"))

        usuario_sem_conta = get_user_model().objects.create_user(
            username="sem_conta_antiga",
            configuracao_inicial_concluida=True,
        )
        self.client.force_login(usuario_sem_conta)
        response_sem_conta = self.client.get(reverse("usuarios:perfil"))

        self.assertNotContains(response_sem_conta, "Consultar contas antigas")
        self.assertNotContains(response_sem_conta, reverse("contas:lista"))

    def test_previa_nao_compartilha_e_confirmacao_vincula_sem_copiar(self):
        dados = {
            "alcance": "todo_historico",
            "contas": [self.conta.pk],
            "cartoes": [],
            "acao": "visualizar",
        }
        response = self.client.post(reverse("usuarios:compartilhamento"), dados)
        self.assertContains(response, "Prévia do alcance")
        self.conta.refresh_from_db()
        self.entrada.refresh_from_db()
        self.assertIsNone(self.conta.sala_compartilhada_id)
        self.assertIsNone(self.entrada.sala_compartilhada_id)

        dados["acao"] = "confirmar"
        response = self.client.post(reverse("usuarios:compartilhamento"), dados)
        self.assertRedirects(response, reverse("usuarios:compartilhamento"))
        self.conta.refresh_from_db()
        self.entrada.refresh_from_db()
        self.assertEqual(self.conta.sala_compartilhada_id, self.sala.pk)
        self.assertEqual(self.entrada.sala_compartilhada_id, self.sala.pk)
        self.assertEqual(Entrada.objects.filter(pk=self.entrada.pk).count(), 1)

    def test_fluxo_retroativo_inclui_lancamentos_rapidos_sem_conta(self):
        entrada_rapida = Entrada.objects.create(
            proprietario_usuario=self.usuario,
            autor=self.usuario,
            pessoa=self.usuario,
            tipo=TipoEntrada.EXTRA,
            descricao="Entrada rápida",
            valor=Decimal("200.00"),
            data=date(2026, 10, 5),
            conta_destino=None,
            dizimo_previsto=Decimal("0.00"),
        )
        saida_rapida = Saida.objects.create(
            proprietario_usuario=self.usuario,
            autor=self.usuario,
            responsavel=self.usuario,
            descricao="Saída rápida",
            valor=Decimal("80.00"),
            situacao=Saida.Situacao.PAGA,
            vencimento=date(2026, 10, 6),
            data_pagamento=date(2026, 10, 6),
            conta=None,
        )

        response = self.client.post(
            reverse("usuarios:compartilhamento"),
            {
                "alcance": "todo_historico",
                "contas": [],
                "cartoes": [],
                "acao": "confirmar",
            },
        )

        self.assertRedirects(response, reverse("usuarios:compartilhamento"))
        entrada_rapida.refresh_from_db()
        saida_rapida.refresh_from_db()
        self.assertEqual(entrada_rapida.sala_compartilhada, self.sala)
        self.assertEqual(saida_rapida.sala_compartilhada, self.sala)
        self.assertEqual(entrada_rapida.proprietario_usuario, self.usuario)
        self.assertEqual(saida_rapida.proprietario_usuario, self.usuario)

    def test_nova_confirmacao_revoga_lancamentos_fora_do_escopo(self):
        self.entrada.sala_compartilhada = self.sala
        self.entrada.save(update_fields=["sala_compartilhada"])

        response = self.client.post(
            reverse("usuarios:compartilhamento"),
            {
                "alcance": "nenhum",
                "contas": [],
                "cartoes": [],
                "acao": "confirmar",
            },
        )

        self.assertRedirects(response, reverse("usuarios:compartilhamento"))
        self.entrada.refresh_from_db()
        self.assertIsNone(self.entrada.sala_compartilhada)


class AvatarFlowTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="avatar_pendente",
            email="avatar@example.com",
            foto_url="https://example.com/google-photo.jpg",
            configuracao_inicial_concluida=True,
        )
        self.client.force_login(self.usuario)

    def test_usuario_com_avatar_pendente_e_encaminhado_ao_editor(self):
        response = self.client.get(reverse("dashboard:mensal"))

        self.assertRedirects(response, reverse("usuarios:avatar"))
        editor = self.client.get(reverse("usuarios:avatar"))
        self.assertContains(editor, "Crie seu avatar")
        self.assertContains(editor, 'name="avatar_v2_base"')
        self.assertContains(editor, 'name="avatar_v2_pele"')
        self.assertContains(editor, 'name="avatar_v2_cabelo"')
        self.assertContains(editor, 'name="avatar_v2_cor_cabelo"')
        self.assertContains(editor, 'name="avatar_v2_barba"')
        self.assertContains(editor, 'name="avatar_v2_roupa"')
        self.assertContains(editor, 'name="avatar_v2_cor_roupa"')
        self.assertContains(editor, "Salvar avatar")
        self.assertContains(editor, "Cancelar")
        self.assertContains(editor, 'data-avatar-has-saved="false"')
        self.assertNotContains(editor, "Personalizar depois")
        self.assertNotContains(editor, self.usuario.foto_url)

    def test_avatar_valido_e_salvo_e_nao_repete_no_proximo_login(self):
        response = self.client.post(
            reverse("usuarios:avatar"),
            {
                "avatar_v2_base": "feminina",
                "avatar_v2_pele": "escura",
                "avatar_v2_cabelo": "comprido",
                "avatar_v2_cor_cabelo": "preto",
                "avatar_v2_barba": "sem_barba",
                "avatar_v2_roupa": "camiseta",
                "avatar_v2_cor_roupa": "coral",
            },
        )

        self.assertRedirects(response, reverse("dashboard:mensal"))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.avatar_concluido)
        self.assertEqual(self.usuario.avatar_versao, 2)
        self.assertEqual(self.usuario.avatar_v2_base, "feminina")
        self.assertEqual(self.usuario.avatar_v2_pele, "escura")
        self.assertEqual(self.usuario.avatar_v2_cabelo, "comprido")
        self.assertEqual(self.usuario.avatar_v2_cor_roupa, "coral")

        self.client.logout()
        self.client.force_login(self.usuario)
        self.assertRedirects(
            self.client.get(reverse("core:home")),
            reverse("dashboard:mensal"),
        )

    def test_opcao_de_avatar_invalida_nao_conclui_etapa(self):
        response = self.client.post(
            reverse("usuarios:avatar"),
            {
                "avatar_v2_base": "inexistente",
                "avatar_v2_pele": "media",
                "avatar_v2_cabelo": "curto",
                "avatar_v2_cor_cabelo": "preto",
                "avatar_v2_barba": "sem_barba",
                "avatar_v2_roupa": "camiseta",
                "avatar_v2_cor_roupa": "azul",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.avatar_concluido)
        self.assertEqual(self.usuario.avatar_versao, 1)

    def test_combinacao_de_roupa_invalida_e_rejeitada(self):
        response = self.client.post(
            reverse("usuarios:avatar"),
            {
                "avatar_v2_base": "masculina",
                "avatar_v2_pele": "media",
                "avatar_v2_cabelo": "curto",
                "avatar_v2_cor_cabelo": "castanho",
                "avatar_v2_barba": "sem_barba",
                "avatar_v2_roupa": "camisa_azul",
                "avatar_v2_cor_roupa": "coral",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A camisa azul não permite escolher outra cor.")
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.avatar_versao, 1)

    def test_erro_ao_salvar_preserva_a_referencia_anterior(self):
        self.usuario.avatar_concluido = True
        self.usuario.avatar_versao = 2
        self.usuario.avatar_v2_base = "feminina"
        self.usuario.avatar_v2_cabelo = "comprido"
        self.usuario.avatar_v2_roupa = "camiseta"
        self.usuario.avatar_v2_cor_roupa = "verde"
        self.usuario.save()

        response = self.client.post(
            reverse("usuarios:avatar"),
            {
                "avatar_v2_base": "masculina",
                "avatar_v2_pele": "media",
                "avatar_v2_cabelo": "curto",
                "avatar_v2_cor_cabelo": "castanho",
                "avatar_v2_barba": "curta",
                "avatar_v2_roupa": "camisa_azul",
                "avatar_v2_cor_roupa": "coral",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-saved-base="feminina"')
        self.assertContains(response, 'data-saved-hair="comprido"')
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.avatar_v2_base, "feminina")
        self.assertEqual(self.usuario.avatar_v2_cabelo, "comprido")
        self.assertEqual(self.usuario.avatar_v2_roupa, "camiseta")
        self.assertEqual(self.usuario.avatar_v2_cor_roupa, "verde")

    def test_post_nao_altera_avatar_de_outro_usuario(self):
        outro = get_user_model().objects.create_user(
            username="outro_avatar",
            avatar_concluido=True,
        )
        dados = {
            "usuario_id": outro.pk,
            "avatar_v2_base": "masculina",
            "avatar_v2_pele": "clara",
            "avatar_v2_cabelo": "sem_cabelo",
            "avatar_v2_cor_cabelo": "grisalho",
            "avatar_v2_barba": "curta",
            "avatar_v2_roupa": "camiseta",
            "avatar_v2_cor_roupa": "verde",
        }

        self.client.post(reverse("usuarios:avatar"), dados)

        outro.refresh_from_db()
        self.assertEqual(outro.avatar_versao, 1)
        self.assertEqual(outro.avatar_v2_cabelo, "curto")

    def test_avatar_antigo_permanece_ate_salvar_a_versao_nova(self):
        self.usuario.avatar_concluido = True
        self.usuario.avatar_pele = "escura"
        self.usuario.avatar_versao = 1
        self.usuario.save(update_fields=["avatar_concluido", "avatar_pele", "avatar_versao"])

        response = self.client.get(reverse("usuarios:perfil"))

        self.assertContains(response, 'data-pele="escura"')
        self.assertNotContains(response, "data-dropduo-avatar-v2")

    def test_cancelar_edicao_nao_altera_avatar_salvo(self):
        self.usuario.avatar_concluido = True
        self.usuario.avatar_versao = 2
        self.usuario.avatar_v2_cabelo = "comprido"
        self.usuario.save(update_fields=["avatar_concluido", "avatar_versao", "avatar_v2_cabelo"])

        editor = self.client.get(
            reverse("usuarios:avatar"),
            {"next": reverse("usuarios:perfil")},
        )
        self.assertContains(editor, f'href="{reverse("usuarios:perfil")}">Cancelar</a>')
        self.client.get(reverse("usuarios:perfil"))

        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.avatar_versao, 2)
        self.assertEqual(self.usuario.avatar_v2_cabelo, "comprido")

    def test_avatar_v2_salvo_aparece_no_perfil_com_mesma_configuracao(self):
        self.usuario.avatar_concluido = True
        self.usuario.avatar_versao = 2
        self.usuario.avatar_v2_base = "feminina"
        self.usuario.avatar_v2_pele = "morena"
        self.usuario.avatar_v2_cabelo = "comprido"
        self.usuario.avatar_v2_cor_cabelo = "ruivo"
        self.usuario.avatar_v2_barba = "sem_barba"
        self.usuario.avatar_v2_roupa = "camiseta"
        self.usuario.avatar_v2_cor_roupa = "verde"
        self.usuario.save()

        response = self.client.get(reverse("usuarios:perfil"))

        self.assertContains(response, "data-dropduo-avatar-v2")
        self.assertContains(response, 'data-avatar-base="feminina"')
        self.assertContains(response, 'data-avatar-pele="morena"')
        self.assertContains(response, 'data-avatar-cabelo="comprido"')
        self.assertContains(response, 'data-avatar-cor-cabelo="ruivo"')
        self.assertContains(response, 'data-avatar-cor-roupa="verde"')
        self.assertContains(response, 'data-avatar-variant="portrait"')
        self.assertNotContains(response, "dropduo-avatar__frame")

    def test_editor_informa_separadamente_o_avatar_salvo(self):
        self.usuario.avatar_concluido = True
        self.usuario.avatar_versao = 2
        self.usuario.avatar_v2_base = "feminina"
        self.usuario.avatar_v2_cabelo = "comprido"
        self.usuario.avatar_v2_cor_cabelo = "ruivo"
        self.usuario.avatar_v2_roupa = "camiseta"
        self.usuario.avatar_v2_cor_roupa = "verde"
        self.usuario.save()

        response = self.client.get(reverse("usuarios:avatar"))

        self.assertContains(response, 'data-avatar-has-saved="true"')
        self.assertContains(response, 'data-saved-base="feminina"')
        self.assertContains(response, 'data-saved-hair="comprido"')
        self.assertContains(response, 'data-saved-hair-color="ruivo"')
        self.assertContains(response, 'data-saved-shirt-color="verde"')

    def test_avatar_do_cabecalho_abre_diretamente_o_editor(self):
        self.usuario.avatar_concluido = True
        self.usuario.avatar_versao = 2
        self.usuario.save(update_fields=["avatar_concluido", "avatar_versao"])

        response = self.client.get(reverse("dashboard:mensal"))

        destino = reverse("usuarios:avatar")
        self.assertContains(response, 'class="dd-avatar-link"')
        self.assertContains(response, f'href="{destino}?next=')
        self.assertContains(response, 'aria-label="Editar meu avatar"')
        self.assertContains(response, f'href="{reverse("usuarios:perfil")}"')

    def test_avatar_v2_usa_a_mesma_configuracao_na_sala(self):
        self.usuario.avatar_concluido = True
        self.usuario.avatar_versao = 2
        self.usuario.avatar_v2_base = "feminina"
        self.usuario.avatar_v2_cabelo = "comprido"
        self.usuario.save()
        sala = Sala.objects.create(
            nome="Sala do avatar",
            orcamento_mensal=Decimal("1000.00"),
            criado_por=self.usuario,
        )
        MembroSala.objects.create(sala=sala, usuario=self.usuario)
        sessao = self.client.session
        sessao["espaco_financeiro"] = "sala"
        sessao.save()

        response = self.client.get(reverse("dashboard:mensal"))

        self.assertContains(response, "data-dropduo-avatar-v2")
        self.assertContains(response, 'data-avatar-base="feminina"')
        self.assertContains(response, 'data-avatar-cabelo="comprido"')

    def test_salvamento_exige_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.usuario)

        response = client.post(
            reverse("usuarios:avatar"),
            {
                "avatar_v2_base": "masculina",
                "avatar_v2_pele": "media",
                "avatar_v2_cabelo": "curto",
                "avatar_v2_cor_cabelo": "castanho",
                "avatar_v2_barba": "sem_barba",
                "avatar_v2_roupa": "camiseta",
                "avatar_v2_cor_roupa": "creme",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.avatar_versao, 1)
