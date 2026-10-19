from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from entradas.models import Entrada, TipoEntrada
from salas.models import MembroSala, Sala

from .models import CartaoCredito, Conta


class ContaModelTests(TestCase):
    def setUp(self):
        self.criador = get_user_model().objects.create_user(username="criador")
        self.externo = get_user_model().objects.create_user(username="externo")
        self.sala = Sala.objects.create(
            nome="Nossa casa",
            orcamento_mensal=Decimal("3000.00"),
            criado_por=self.criador,
        )
        MembroSala.objects.create(sala=self.sala, usuario=self.criador)

    def test_titular_da_conta_deve_participar_da_sala(self):
        conta = Conta(
            sala=self.sala,
            tipo=Conta.Tipo.DINHEIRO,
            nome="Carteira",
            titular=self.externo,
            saldo_inicial=Decimal("100.00"),
            data_saldo_inicial=date(2026, 10, 1),
        )

        with self.assertRaisesMessage(ValidationError, "participante da sala"):
            conta.full_clean()

    def test_titular_do_cartao_deve_participar_da_sala(self):
        cartao = CartaoCredito(
            sala=self.sala,
            nome="Cartão principal",
            titular=self.externo,
            dia_fechamento=10,
            dia_vencimento=17,
        )

        with self.assertRaisesMessage(ValidationError, "participante da sala"):
            cartao.full_clean()

    def test_dias_do_cartao_sao_ajustados_para_meses_mais_curtos(self):
        cartao = CartaoCredito(
            sala=self.sala,
            nome="Cartão dia 31",
            titular=self.criador,
            dia_fechamento=31,
            dia_vencimento=30,
        )

        self.assertEqual(cartao.data_fechamento_no_mes(2026, 2), date(2026, 2, 28))
        self.assertEqual(cartao.data_fechamento_no_mes(2028, 2), date(2028, 2, 29))
        self.assertEqual(cartao.data_vencimento_no_mes(2026, 4), date(2026, 4, 30))

    def test_cartao_nao_armazena_dados_sensiveis_desnecessarios(self):
        campos = {campo.name for campo in CartaoCredito._meta.fields}

        self.assertNotIn("numero", campos)
        self.assertNotIn("validade", campos)
        self.assertNotIn("codigo_seguranca", campos)
        self.assertNotIn("limite", campos)

    def test_saldo_considera_apenas_entradas_recebidas(self):
        conta = Conta.objects.create(
            sala=self.sala,
            tipo=Conta.Tipo.DINHEIRO,
            nome="Conta principal",
            titular=self.criador,
            saldo_inicial=Decimal("100.00"),
            data_saldo_inicial=date(2026, 10, 1),
        )
        dados_comuns = {
            "sala": self.sala,
            "pessoa": self.criador,
            "tipo": TipoEntrada.SALARIO,
            "valor": Decimal("200.00"),
            "conta_destino": conta,
        }
        Entrada.objects.create(
            **dados_comuns,
            descricao="Recebida",
            situacao=Entrada.Situacao.RECEBIDA,
            data_prevista=date(2026, 10, 10),
            data=date(2026, 10, 10),
        )
        Entrada.objects.create(
            **dados_comuns,
            descricao="Prevista",
            situacao=Entrada.Situacao.A_RECEBER,
            data_prevista=date(2026, 11, 10),
        )
        Entrada.objects.create(
            **dados_comuns,
            descricao="Cancelada",
            situacao=Entrada.Situacao.CANCELADA,
            data_prevista=date(2026, 12, 10),
        )

        self.assertEqual(conta.saldo_atual, Decimal("300.00"))


class CadastroContasTests(TestCase):
    def setUp(self):
        self.criador = get_user_model().objects.create_user(
            username="criador",
            first_name="João",
        )
        self.parceira = get_user_model().objects.create_user(
            username="parceira",
            first_name="Maria",
        )
        self.externo = get_user_model().objects.create_user(username="externo")
        self.sala = Sala.objects.create(
            nome="Nossa casa",
            orcamento_mensal=Decimal("3000.00"),
            criado_por=self.criador,
        )
        MembroSala.objects.create(sala=self.sala, usuario=self.criador)
        MembroSala.objects.create(sala=self.sala, usuario=self.parceira)

        self.outra_sala = Sala.objects.create(
            nome="Sala externa",
            orcamento_mensal=Decimal("1000.00"),
            criado_por=self.externo,
        )
        MembroSala.objects.create(sala=self.outra_sala, usuario=self.externo)
        sessao = self.client.session
        sessao["espaco_financeiro"] = "sala"
        sessao.save()

    def criar_conta(self, tipo=Conta.Tipo.DINHEIRO):
        return Conta.objects.create(
            sala=self.sala,
            tipo=tipo,
            nome="Conta teste",
            titular=self.criador,
            saldo_inicial=Decimal("150.00"),
            data_saldo_inicial=date(2026, 10, 1),
        )

    def criar_cartao(self):
        return CartaoCredito.objects.create(
            sala=self.sala,
            nome="Cartão principal",
            titular=self.criador,
            dia_fechamento=8,
            dia_vencimento=15,
        )

    def test_paginas_exigem_login(self):
        response_lista = self.client.get(reverse("contas:lista"))
        response_nova_conta = self.client.get(reverse("contas:criar_conta"))
        response_novo_cartao = self.client.get(reverse("contas:criar_cartao"))

        self.assertEqual(response_lista.status_code, 302)
        self.assertEqual(response_nova_conta.status_code, 302)
        self.assertEqual(response_novo_cartao.status_code, 302)

    def test_cadastra_conta_em_dinheiro(self):
        self.client.force_login(self.criador)

        response = self.client.post(
            reverse("contas:criar_conta"),
            {
                "tipo": Conta.Tipo.DINHEIRO,
                "nome": "Dinheiro da casa",
                "titular": self.criador.pk,
                "saldo_inicial": "250.75",
                "data_saldo_inicial": "2026-10-01",
            },
        )

        self.assertRedirects(response, reverse("contas:lista"))
        conta = Conta.objects.get(nome="Dinheiro da casa")
        self.assertEqual(conta.sala, self.sala)
        self.assertEqual(conta.saldo_inicial, Decimal("250.75"))

    def test_dinheiro_e_vale_mantem_saldos_separados(self):
        dinheiro = self.criar_conta(Conta.Tipo.DINHEIRO)
        vale = Conta.objects.create(
            sala=self.sala,
            tipo=Conta.Tipo.VALE_ALIMENTACAO,
            nome="Vale mercado",
            titular=self.parceira,
            saldo_inicial=Decimal("600.00"),
            data_saldo_inicial=date(2026, 10, 1),
        )

        self.assertEqual(dinheiro.saldo_inicial, Decimal("150.00"))
        self.assertEqual(vale.saldo_inicial, Decimal("600.00"))
        self.assertNotEqual(dinheiro.pk, vale.pk)

    def test_cadastra_cartao_sem_dados_sensiveis(self):
        self.client.force_login(self.parceira)

        response = self.client.post(
            reverse("contas:criar_cartao"),
            {
                "nome": "Cartão do casal",
                "titular": self.parceira.pk,
                "dia_fechamento": "31",
                "dia_vencimento": "5",
            },
        )

        self.assertRedirects(response, reverse("cartoes:lista"))
        cartao = CartaoCredito.objects.get(nome="Cartão do casal")
        self.assertEqual(cartao.sala, self.sala)
        self.assertEqual(cartao.dia_fechamento, 31)

    def test_dia_maior_que_31_e_recusado(self):
        self.client.force_login(self.criador)

        response = self.client.post(
            reverse("contas:criar_cartao"),
            {
                "nome": "Cartão inválido",
                "titular": self.criador.pk,
                "dia_fechamento": "32",
                "dia_vencimento": "10",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CartaoCredito.objects.filter(nome="Cartão inválido").exists())
        self.assertContains(response, "Certifique-se que este valor seja menor ou igual a 31")

    def test_titular_adulterado_no_formulario_e_recusado(self):
        self.client.force_login(self.criador)

        response = self.client.post(
            reverse("contas:criar_conta"),
            {
                "tipo": Conta.Tipo.DINHEIRO,
                "nome": "Conta adulterada",
                "titular": self.externo.pk,
                "saldo_inicial": "100.00",
                "data_saldo_inicial": "2026-10-01",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Conta.objects.filter(nome="Conta adulterada").exists())
        self.assertContains(response, "Faça uma escolha válida")

    def test_os_dois_membros_podem_editar_conta(self):
        conta = self.criar_conta()
        self.client.force_login(self.parceira)

        response = self.client.post(
            reverse("contas:editar_conta", args=[conta.pk]),
            {
                "tipo": Conta.Tipo.DINHEIRO,
                "nome": "Conta atualizada",
                "titular": self.parceira.pk,
                "saldo_inicial": "200.00",
                "data_saldo_inicial": "2026-10-02",
            },
        )

        self.assertRedirects(response, reverse("contas:lista"))
        conta.refresh_from_db()
        self.assertEqual(conta.nome, "Conta atualizada")
        self.assertEqual(conta.titular, self.parceira)

    def test_os_dois_membros_podem_editar_cartao(self):
        cartao = self.criar_cartao()
        self.client.force_login(self.parceira)

        response = self.client.post(
            reverse("contas:editar_cartao", args=[cartao.pk]),
            {
                "nome": "Cartão atualizado",
                "titular": self.parceira.pk,
                "dia_fechamento": "12",
                "dia_vencimento": "20",
            },
        )

        self.assertRedirects(
            response,
            reverse("cartoes:detalhe_cartao", args=[cartao.pk]),
        )
        cartao.refresh_from_db()
        self.assertEqual(cartao.nome, "Cartão atualizado")
        self.assertEqual(cartao.titular, self.criador)

    def test_usuario_externo_nao_consulta_nem_edita_cadastros_da_sala(self):
        conta = self.criar_conta()
        cartao = self.criar_cartao()
        self.client.force_login(self.externo)

        response_lista = self.client.get(reverse("contas:lista"))
        response_conta = self.client.get(
            reverse("contas:editar_conta", args=[conta.pk])
        )
        response_cartao = self.client.get(
            reverse("contas:editar_cartao", args=[cartao.pk])
        )

        self.assertNotContains(response_lista, conta.nome)
        self.assertNotContains(response_lista, cartao.nome)
        self.assertEqual(response_conta.status_code, 404)
        self.assertEqual(response_cartao.status_code, 404)

    def test_lista_separa_dinheiro_vale_e_cartao(self):
        dinheiro = self.criar_conta(Conta.Tipo.DINHEIRO)
        vale = Conta.objects.create(
            sala=self.sala,
            tipo=Conta.Tipo.VALE_ALIMENTACAO,
            nome="Vale mercado",
            titular=self.parceira,
            saldo_inicial=Decimal("500.00"),
            data_saldo_inicial=date(2026, 10, 1),
        )
        cartao = self.criar_cartao()
        self.client.force_login(self.criador)

        response_contas = self.client.get(reverse("contas:lista"))
        response_cartoes = self.client.get(reverse("cartoes:lista"))

        self.assertContains(response_contas, dinheiro.nome)
        self.assertContains(response_contas, vale.nome)
        self.assertNotContains(response_contas, cartao.nome)
        self.assertContains(response_contas, "Contas em dinheiro")
        self.assertContains(response_contas, "Vales-alimentação")
        self.assertContains(response_cartoes, cartao.nome)
        self.assertContains(response_cartoes, "Cartões")

    def test_cadastra_regras_de_ultimo_dia_sem_campos_numericos(self):
        self.client.force_login(self.criador)

        response = self.client.post(
            reverse("contas:criar_cartao"),
            {
                "nome": "Cartão último dia",
                "cor_simbolo": CartaoCredito.CorSimbolo.VERDE,
                "regra_fechamento": CartaoCredito.RegraData.ULTIMO_DIA,
                "regra_vencimento": CartaoCredito.RegraData.ULTIMO_DIA,
            },
        )

        self.assertEqual(response.status_code, 302)
        cartao = CartaoCredito.objects.get(nome="Cartão último dia")
        self.assertIsNone(cartao.dia_fechamento)
        self.assertIsNone(cartao.dia_vencimento)
        self.assertEqual(cartao.cor_simbolo, CartaoCredito.CorSimbolo.VERDE)

    def test_cartao_vermelho_pode_ser_criado_editado_e_exibido(self):
        self.client.force_login(self.criador)
        dados = {
            "nome": "Cartão vermelho",
            "cor_simbolo": CartaoCredito.CorSimbolo.VERMELHO,
            "regra_fechamento": CartaoCredito.RegraData.DIA_FIXO,
            "dia_fechamento": "20",
            "regra_vencimento": CartaoCredito.RegraData.DIA_FIXO,
            "dia_vencimento": "5",
        }

        response = self.client.post(reverse("contas:criar_cartao"), dados)

        self.assertEqual(response.status_code, 302)
        cartao = CartaoCredito.objects.get(nome="Cartão vermelho")
        self.assertEqual(cartao.cor_simbolo, CartaoCredito.CorSimbolo.VERMELHO)
        self.assertEqual(cartao.caminho_simbolo, "dropduo/cards/cartao-vermelho.svg")
        self.assertContains(
            self.client.get(reverse("contas:editar_cartao", args=[cartao.pk])),
            "dropduo/cards/cartao-vermelho.svg",
        )
        dados["nome"] = "Cartão vermelho editado"
        response = self.client.post(
            reverse("contas:editar_cartao", args=[cartao.pk]),
            dados,
        )
        self.assertEqual(response.status_code, 302)
        cartao.refresh_from_db()
        self.assertEqual(cartao.cor_simbolo, CartaoCredito.CorSimbolo.VERMELHO)
        self.assertEqual(cartao.nome, "Cartão vermelho editado")
        self.assertContains(
            self.client.get(reverse("cartoes:lista")),
            "dropduo/cards/cartao-vermelho.svg",
        )
        self.assertContains(
            self.client.get(reverse("core:lancamentos"), {"tipo": "saida"}),
            "dropduo/cards/cartao-vermelho.svg",
        )

    def test_dia_fixo_trinta_e_um_permanece_dia_fixo(self):
        self.client.force_login(self.criador)

        self.client.post(
            reverse("contas:criar_cartao"),
            {
                "nome": "Cartão dia 31",
                "cor_simbolo": CartaoCredito.CorSimbolo.AZUL,
                "regra_fechamento": CartaoCredito.RegraData.DIA_FIXO,
                "dia_fechamento": "31",
                "regra_vencimento": CartaoCredito.RegraData.DIA_FIXO,
                "dia_vencimento": "8",
            },
        )

        cartao = CartaoCredito.objects.get(nome="Cartão dia 31")
        self.assertEqual(cartao.regra_fechamento, CartaoCredito.RegraData.DIA_FIXO)
        self.assertEqual(cartao.dia_fechamento, 31)
