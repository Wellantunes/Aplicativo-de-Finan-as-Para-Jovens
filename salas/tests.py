from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from .models import ConviteSala, MembroSala, Sala
from .services import SalaErro, aceitar_convite


class SalaModelTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(username="criador")

    def test_orcamento_zero_e_valido(self):
        sala = Sala(
            nome="Nossa casa",
            orcamento_mensal=Decimal("0.00"),
            criado_por=self.usuario,
        )

        sala.full_clean()

    def test_orcamento_negativo_e_recusado(self):
        sala = Sala(
            nome="Nossa casa",
            orcamento_mensal=Decimal("-0.01"),
            criado_por=self.usuario,
        )

        with self.assertRaises(ValidationError):
            sala.full_clean()


class FluxoSalaTests(TestCase):
    def setUp(self):
        self.criador = get_user_model().objects.create_user(
            username="criador",
            first_name="João",
            email="joao@example.com",
            foto_url="https://example.com/joao.jpg",
        )
        self.parceira = get_user_model().objects.create_user(
            username="parceira",
            first_name="Maria",
            email="maria@example.com",
        )

    def criar_sala_com_convite(self, codigo="CASAL123"):
        sala = Sala.objects.create(
            nome="Nossa casa",
            orcamento_mensal=Decimal("3500.00"),
            criado_por=self.criador,
        )
        MembroSala.objects.create(sala=sala, usuario=self.criador)
        convite = ConviteSala.objects.create(
            sala=sala,
            codigo=codigo,
            criado_por=self.criador,
        )
        return sala, convite

    def test_paginas_exigem_login(self):
        response_criar = self.client.get(reverse("salas:criar"))
        response_entrar = self.client.get(reverse("salas:entrar"))

        self.assertEqual(response_criar.status_code, 302)
        self.assertEqual(response_entrar.status_code, 302)

    def test_cria_sala_com_membro_e_convite_valido_por_24_horas(self):
        self.client.force_login(self.criador)
        antes = timezone.now() + timedelta(hours=24)

        response = self.client.post(
            reverse("salas:criar"),
            {"nome": "Nosso lar", "orcamento_mensal": "0"},
        )

        sala = Sala.objects.get()
        convite = sala.convites.get()
        self.assertRedirects(response, reverse("salas:detalhe", args=[sala.pk]))
        self.assertEqual(sala.orcamento_mensal, Decimal("0"))
        self.assertTrue(sala.membros.filter(usuario=self.criador).exists())
        self.assertGreaterEqual(convite.expira_em, antes)
        self.assertLessEqual(convite.expira_em, antes + timedelta(minutes=1))

    def test_formulario_recusa_orcamento_negativo(self):
        self.client.force_login(self.criador)

        response = self.client.post(
            reverse("salas:criar"),
            {"nome": "Nosso lar", "orcamento_mensal": "-1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Sala.objects.exists())
        self.assertContains(response, "Certifique-se que este valor seja maior ou igual a 0")

    def test_exibe_nome_da_sala_antes_da_confirmacao(self):
        sala, convite = self.criar_sala_com_convite()
        self.client.force_login(self.parceira)

        response = self.client.get(
            reverse("salas:confirmar_entrada", args=[convite.codigo])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, sala.nome)
        self.assertContains(response, "Confirmar participação")

    def test_parceira_aceita_convite_e_passa_a_ver_a_sala(self):
        sala, convite = self.criar_sala_com_convite()
        self.client.force_login(self.parceira)

        response = self.client.post(
            reverse("salas:confirmar_entrada", args=[convite.codigo])
        )

        self.assertRedirects(response, reverse("salas:detalhe", args=[sala.pk]))
        self.assertEqual(sala.membros.count(), 2)
        convite.refresh_from_db()
        self.assertIsNotNone(convite.usado_em)
        self.assertEqual(convite.usado_por, self.parceira)

        detail_response = self.client.get(reverse("salas:detalhe", args=[sala.pk]))
        self.assertContains(detail_response, "João")
        self.assertContains(detail_response, "Maria")
        self.assertNotContains(detail_response, self.criador.foto_url)
        self.assertContains(detail_response, "data-avatar-figure", count=3)

    def test_cria_sala_de_amigos_com_bau_como_padrao(self):
        self.client.force_login(self.criador)

        response = self.client.post(
            reverse("salas:criar"),
            {
                "nome": "República",
                "tipo": Sala.Tipo.AMIGOS,
                "simbolo": "",
                "orcamento_mensal": "1500.00",
            },
        )

        sala = Sala.objects.get()
        self.assertRedirects(response, reverse("salas:detalhe", args=[sala.pk]))
        self.assertEqual(sala.tipo, Sala.Tipo.AMIGOS)
        self.assertEqual(sala.simbolo, Sala.Simbolo.BAU)

    def test_membro_pode_editar_tipo_e_simbolo_sem_alterar_financas(self):
        sala, _ = self.criar_sala_com_convite()
        self.client.force_login(self.criador)

        response = self.client.post(
            reverse("salas:configurar", args=[sala.pk]),
            {
                "nome": sala.nome,
                "tipo": Sala.Tipo.AMIGOS,
                "simbolo": Sala.Simbolo.BAU,
                "orcamento_mensal": "3500.00",
            },
        )

        self.assertRedirects(response, reverse("salas:detalhe", args=[sala.pk]))
        sala.refresh_from_db()
        self.assertEqual(sala.tipo, Sala.Tipo.AMIGOS)
        self.assertEqual(sala.simbolo, Sala.Simbolo.BAU)
        self.assertEqual(sala.orcamento_mensal, Decimal("3500.00"))
        self.assertEqual(sala.membros.count(), 1)

    def test_usuario_externo_nao_edita_configuracoes_da_sala(self):
        sala, _ = self.criar_sala_com_convite()
        externo = get_user_model().objects.create_user(username="externo_config")
        self.client.force_login(externo)

        response = self.client.post(
            reverse("salas:configurar", args=[sala.pk]),
            {
                "nome": "Nome indevido",
                "tipo": Sala.Tipo.AMIGOS,
                "simbolo": Sala.Simbolo.BAU,
                "orcamento_mensal": "1.00",
            },
        )

        self.assertEqual(response.status_code, 404)
        sala.refresh_from_db()
        self.assertEqual(sala.nome, "Nossa casa")

    def test_formulario_recusa_simbolo_sem_asset_disponivel(self):
        self.client.force_login(self.criador)

        response = self.client.post(
            reverse("salas:criar"),
            {
                "nome": "República",
                "tipo": Sala.Tipo.AMIGOS,
                "simbolo": "escudo",
                "orcamento_mensal": "1500.00",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Sala.objects.exists())
        self.assertContains(response, "Faça uma escolha válida")

    def test_preferencia_de_dizimo_da_sala_pode_ser_criada_e_alterada(self):
        self.client.force_login(self.criador)
        self.client.post(
            reverse("salas:criar"),
            {
                "nome": "Sala com dízimos",
                "orcamento_mensal": "1000.00",
                "controlar_dizimos": "on",
            },
        )
        sala = Sala.objects.get()
        self.assertTrue(sala.controlar_dizimos)

        response = self.client.post(
            reverse("salas:configurar", args=[sala.pk]),
            {
                "nome": sala.nome,
                "tipo": sala.tipo,
                "simbolo": sala.simbolo,
                "orcamento_mensal": sala.orcamento_mensal,
            },
        )

        self.assertRedirects(response, reverse("salas:detalhe", args=[sala.pk]))
        sala.refresh_from_db()
        self.assertFalse(sala.controlar_dizimos)

    def test_codigo_invalido_e_recusado(self):
        self.client.force_login(self.parceira)

        response = self.client.get(
            reverse("salas:confirmar_entrada", args=["INVALIDO"]),
            follow=True,
        )

        self.assertContains(response, "Código de convite inválido")
        self.assertFalse(MembroSala.objects.filter(usuario=self.parceira).exists())

    def test_codigo_expirado_e_recusado(self):
        _, convite = self.criar_sala_com_convite()
        convite.expira_em = timezone.now() - timedelta(seconds=1)
        convite.save(update_fields=["expira_em"])
        self.client.force_login(self.parceira)

        response = self.client.get(
            reverse("salas:confirmar_entrada", args=[convite.codigo]),
            follow=True,
        )

        self.assertContains(response, "Este convite expirou")
        self.assertFalse(MembroSala.objects.filter(usuario=self.parceira).exists())

    def test_codigo_usado_e_recusado(self):
        _, convite = self.criar_sala_com_convite()
        convite.usado_em = timezone.now()
        convite.usado_por = self.criador
        convite.save(update_fields=["usado_em", "usado_por"])
        self.client.force_login(self.parceira)

        response = self.client.get(
            reverse("salas:confirmar_entrada", args=[convite.codigo]),
            follow=True,
        )

        self.assertContains(response, "Este convite já foi utilizado")
        self.assertFalse(MembroSala.objects.filter(usuario=self.parceira).exists())

    def test_terceira_pessoa_nao_entra_na_sala(self):
        sala, _ = self.criar_sala_com_convite()
        MembroSala.objects.create(sala=sala, usuario=self.parceira)
        terceiro = get_user_model().objects.create_user(username="terceiro")
        outro_convite = ConviteSala.objects.create(
            sala=sala,
            codigo="TERC1234",
            criado_por=self.criador,
        )
        self.client.force_login(terceiro)

        response = self.client.get(
            reverse("salas:confirmar_entrada", args=[outro_convite.codigo]),
            follow=True,
        )

        self.assertContains(response, "Esta sala já possui dois participantes")
        self.assertFalse(MembroSala.objects.filter(usuario=terceiro).exists())

    def test_usuario_externo_nao_visualiza_nem_gera_convite(self):
        sala, _ = self.criar_sala_com_convite()
        externo = get_user_model().objects.create_user(username="externo")
        self.client.force_login(externo)

        response_detalhe = self.client.get(reverse("salas:detalhe", args=[sala.pk]))
        response_convite = self.client.post(
            reverse("salas:gerar_convite", args=[sala.pk])
        )

        self.assertEqual(response_detalhe.status_code, 404)
        self.assertEqual(response_convite.status_code, 404)

    def test_limite_e_mantido_com_dois_convites_diferentes(self):
        sala, primeiro_convite = self.criar_sala_com_convite()
        segundo_convite = ConviteSala.objects.create(
            sala=sala,
            codigo="OUTR1234",
            criado_por=self.criador,
        )
        terceiro = get_user_model().objects.create_user(username="terceiro")

        aceitar_convite(self.parceira, primeiro_convite.codigo)
        with self.assertRaisesMessage(SalaErro, "dois participantes"):
            aceitar_convite(terceiro, segundo_convite.codigo)

        self.assertEqual(sala.membros.count(), 2)


@skipUnlessDBFeature("has_select_for_update")
class ConcorrenciaSalaTests(TransactionTestCase):
    def setUp(self):
        self.criador = get_user_model().objects.create_user(username="criador")
        self.candidato_um = get_user_model().objects.create_user(username="candidato_um")
        self.candidato_dois = get_user_model().objects.create_user(username="candidato_dois")
        self.sala = Sala.objects.create(
            nome="Nossa casa",
            orcamento_mensal=Decimal("1000.00"),
            criado_por=self.criador,
        )
        MembroSala.objects.create(sala=self.sala, usuario=self.criador)
        self.convite_um = ConviteSala.objects.create(
            sala=self.sala,
            codigo="SIMUL001",
            criado_por=self.criador,
        )
        self.convite_dois = ConviteSala.objects.create(
            sala=self.sala,
            codigo="SIMUL002",
            criado_por=self.criador,
        )

    def test_duas_aceitacoes_simultaneas_nao_criam_terceiro_membro(self):
        barreira = Barrier(2)

        def tentar_entrar(usuario_id, codigo):
            close_old_connections()
            usuario = get_user_model().objects.get(pk=usuario_id)
            barreira.wait()
            try:
                aceitar_convite(usuario, codigo)
                return True
            except SalaErro:
                return False
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(
                executor.map(
                    lambda dados: tentar_entrar(*dados),
                    [
                        (self.candidato_um.pk, self.convite_um.codigo),
                        (self.candidato_dois.pk, self.convite_dois.codigo),
                    ],
                )
            )

        self.assertEqual(resultados.count(True), 1)
        self.assertEqual(self.sala.membros.count(), 2)
