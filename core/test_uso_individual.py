from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cartoes.models import CompraCredito, Fatura, Parcela
from contas.models import CartaoCredito, Conta
from core.espacos import CHAVE_ESPACO_SESSAO, ESPACO_INDIVIDUAL, ESPACO_SALA
from dashboard.calculos import calcular_dashboard
from entradas.models import Entrada, FormaCalculoDizimo, TipoEntrada
from saidas.models import Saida
from salas.models import MembroSala, Sala


class UsoIndividualECompartilhamentoTests(TestCase):
    def setUp(self):
        Usuario = get_user_model()
        self.wellington = Usuario.objects.create_user(
            username="wellington",
            first_name="Wellington",
            email="wellington@example.com",
            configuracao_inicial_concluida=True,
            avatar_concluido=True,
        )
        self.kawany = Usuario.objects.create_user(
            username="kawany",
            first_name="Kawany",
            email="kawany@example.com",
            configuracao_inicial_concluida=True,
            avatar_concluido=True,
        )
        self.externo = Usuario.objects.create_user(
            username="externo",
            configuracao_inicial_concluida=True,
            avatar_concluido=True,
        )
        self.sala = Sala.objects.create(
            nome="Nossa casa",
            orcamento_mensal=Decimal("2000.00"),
            criado_por=self.wellington,
        )
        MembroSala.objects.create(sala=self.sala, usuario=self.wellington)
        MembroSala.objects.create(sala=self.sala, usuario=self.kawany)
        self.conta_wellington = Conta.objects.create(
            proprietario_usuario=self.wellington,
            sala_compartilhada=self.sala,
            autor=self.wellington,
            titular=self.wellington,
            tipo=Conta.Tipo.DINHEIRO,
            nome="Conta Wellington",
            saldo_inicial=Decimal("1000.00"),
            data_saldo_inicial=date(2026, 1, 1),
        )
        self.conta_kawany = Conta.objects.create(
            proprietario_usuario=self.kawany,
            autor=self.kawany,
            titular=self.kawany,
            tipo=Conta.Tipo.DINHEIRO,
            nome="Conta Kawany",
            saldo_inicial=Decimal("500.00"),
            data_saldo_inicial=date(2026, 1, 1),
        )

    def ativar_espaco(self, espaco):
        sessao = self.client.session
        sessao[CHAVE_ESPACO_SESSAO] = espaco
        sessao.save()

    def criar_entrada(self, usuario, descricao, compartilhada=None, sala=None):
        return Entrada.objects.create(
            proprietario_usuario=None if sala else usuario,
            sala=sala,
            sala_compartilhada=compartilhada,
            autor=usuario,
            pessoa=usuario,
            tipo=TipoEntrada.SALARIO,
            descricao=descricao,
            valor=Decimal("100.00"),
            data=date(2026, 10, 5),
            conta_destino=self.conta_wellington if usuario == self.wellington else self.conta_kawany,
            calcular_dizimo=False,
            forma_calculo="",
            dizimo_previsto=Decimal("0.00"),
        )

    def test_login_abre_individual_mesmo_quando_usuario_tem_sala(self):
        self.client.force_login(self.wellington)
        response = self.client.get(reverse("core:home"))
        self.assertRedirects(response, reverse("dashboard:mensal"))
        self.assertEqual(self.client.session[CHAVE_ESPACO_SESSAO], ESPACO_INDIVIDUAL)

    def test_usuario_sem_sala_cadastra_conta_e_usa_dashboard(self):
        usuario = get_user_model().objects.create_user(
            username="solo",
            configuracao_inicial_concluida=True,
            avatar_concluido=True,
        )
        self.client.force_login(usuario)
        self.ativar_espaco(ESPACO_INDIVIDUAL)
        response = self.client.post(reverse("contas:criar_conta"), {
            "tipo": Conta.Tipo.DINHEIRO,
            "nome": "Minha conta",
            "titular": usuario.pk,
            "saldo_inicial": "250.00",
            "data_saldo_inicial": "2026-10-01",
        })
        self.assertRedirects(response, reverse("contas:lista"))
        self.assertTrue(Conta.objects.filter(proprietario_usuario=usuario).exists())
        self.assertEqual(self.client.get(reverse("dashboard:mensal")).status_code, 200)

    def test_renda_prevista_nao_altera_saldo(self):
        saldo_antes = self.conta_wellington.saldo_atual
        self.wellington.renda_mensal_prevista = Decimal("3500.00")
        self.wellington.save(update_fields=["renda_mensal_prevista"])
        self.conta_wellington.refresh_from_db()
        self.assertEqual(self.conta_wellington.saldo_atual, saldo_antes)

    def test_privado_compartilhado_e_registro_da_sala_tem_visibilidades_distintas(self):
        self.conta_kawany.sala_compartilhada = self.sala
        self.conta_kawany.save(update_fields=["sala_compartilhada"])
        shampoo = self.criar_entrada(self.wellington, "Shampoo", self.sala)
        remedio = self.criar_entrada(self.kawany, "Remédio", self.sala)
        compra_sala = Entrada.objects.create(
            sala=self.sala,
            autor=self.wellington,
            pessoa=self.wellington,
            tipo=TipoEntrada.OUTROS,
            descricao="Entrada da sala",
            valor=Decimal("50.00"),
            data=date(2026, 10, 6),
            conta_destino=self.conta_wellington,
            calcular_dizimo=False,
            forma_calculo="",
            dizimo_previsto=Decimal("0.00"),
        )

        self.client.force_login(self.wellington)
        self.ativar_espaco(ESPACO_INDIVIDUAL)
        response = self.client.get(reverse("entradas:lista"))
        self.assertContains(response, shampoo.descricao)
        self.assertNotContains(response, remedio.descricao)
        self.assertNotContains(response, compra_sala.descricao)

        self.client.force_login(self.kawany)
        self.ativar_espaco(ESPACO_INDIVIDUAL)
        response = self.client.get(reverse("entradas:lista"))
        self.assertContains(response, remedio.descricao)
        self.assertNotContains(response, shampoo.descricao)

        self.ativar_espaco(ESPACO_SALA)
        response = self.client.get(reverse("entradas:lista"))
        self.assertContains(response, shampoo.descricao)
        self.assertContains(response, remedio.descricao)
        self.assertContains(response, compra_sala.descricao)

    def test_parceiro_nao_edita_registro_individual_compartilhado(self):
        entrada = self.criar_entrada(self.wellington, "Privada compartilhada", self.sala)
        self.client.force_login(self.kawany)
        self.ativar_espaco(ESPACO_SALA)
        self.assertEqual(
            self.client.get(reverse("entradas:editar", args=[entrada.pk])).status_code,
            404,
        )

    def test_usuario_externo_nao_acessa_registro_compartilhado(self):
        entrada = self.criar_entrada(self.wellington, "Somente nossa", self.sala)
        self.client.force_login(self.externo)
        self.ativar_espaco(ESPACO_INDIVIDUAL)
        self.assertEqual(
            self.client.get(reverse("entradas:editar", args=[entrada.pk])).status_code,
            404,
        )

    def test_parceiro_perde_acesso_ao_compartilhado_quando_proprietario_sai(self):
        entrada = self.criar_entrada(
            self.wellington,
            "Compartilhada antes da saída",
            self.sala,
        )
        MembroSala.objects.get(usuario=self.wellington).delete()

        self.client.force_login(self.kawany)
        self.ativar_espaco(ESPACO_SALA)
        response = self.client.get(reverse("entradas:lista"))

        self.assertNotContains(response, entrada.descricao)

    def test_sessao_de_sala_invalida_retorna_ao_espaco_individual(self):
        entrada_externa = self.criar_entrada(
            self.wellington,
            "Não pode vazar",
            self.sala,
        )
        self.client.force_login(self.externo)
        self.ativar_espaco(ESPACO_SALA)

        response = self.client.get(reverse("entradas:lista"))

        self.assertNotContains(response, entrada_externa.descricao)
        self.assertEqual(response.context["contexto_espaco"], "Pessoal")

    def test_saida_da_sala_reduz_saldo_real_da_conta_compartilhada(self):
        Saida.objects.create(
            sala=self.sala,
            autor=self.kawany,
            descricao="Mercado da casa",
            valor=Decimal("150.00"),
            responsavel=self.kawany,
            custo_vida=True,
            situacao=Saida.Situacao.PAGA,
            data_pagamento=date(2026, 10, 7),
            forma_pagamento=Saida.FormaPagamento.PIX,
            conta=self.conta_wellington,
        )
        self.assertEqual(self.conta_wellington.saldo_atual, Decimal("850.00"))

    def test_conta_compartilhada_entra_uma_vez_no_dashboard_da_sala(self):
        painel = calcular_dashboard(
            self.sala,
            2026,
            10,
            usuario=self.wellington,
        )
        self.assertEqual(painel["saldo_dinheiro"], Decimal("1000.00"))
        self.assertEqual(len(painel["saldos_dinheiro_contas"]), 1)

    def test_nao_remove_compartilhamento_de_conta_com_movimento_da_sala(self):
        Saida.objects.create(
            sala=self.sala,
            autor=self.wellington,
            descricao="Pagamento compartilhado",
            valor=Decimal("20.00"),
            responsavel=self.wellington,
            situacao=Saida.Situacao.PAGA,
            data_pagamento=date(2026, 10, 8),
            forma_pagamento=Saida.FormaPagamento.PIX,
            conta=self.conta_wellington,
        )
        self.client.force_login(self.wellington)
        self.ativar_espaco(ESPACO_INDIVIDUAL)
        response = self.client.post(
            reverse("contas:editar_conta", args=[self.conta_wellington.pk]),
            {
                "tipo": Conta.Tipo.DINHEIRO,
                "nome": self.conta_wellington.nome,
                "titular": self.wellington.pk,
                "saldo_inicial": "1000.00",
                "data_saldo_inicial": "2026-01-01",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "histórico financeiro inconsistente")
        self.conta_wellington.refresh_from_db()
        self.assertEqual(self.conta_wellington.sala_compartilhada_id, self.sala.pk)

    def test_fatura_mostra_total_real_sem_expor_item_privado_ao_parceiro(self):
        cartao = CartaoCredito.objects.create(
            proprietario_usuario=self.wellington,
            sala_compartilhada=self.sala,
            autor=self.wellington,
            titular=self.wellington,
            nome="Cartão Wellington",
            dia_fechamento=25,
            dia_vencimento=5,
        )
        privada = CompraCredito.objects.create(
            proprietario_usuario=self.wellington,
            autor=self.wellington,
            cartao=cartao,
            responsavel=self.wellington,
            descricao="Compra privada",
            valor_total=Decimal("80.00"),
            data_compra=date(2026, 10, 1),
            quantidade_parcelas=1,
        )
        compartilhada = CompraCredito.objects.create(
            sala=self.sala,
            autor=self.wellington,
            cartao=cartao,
            responsavel=self.wellington,
            descricao="Compra da sala",
            valor_total=Decimal("120.00"),
            data_compra=date(2026, 10, 2),
            quantidade_parcelas=1,
        )
        fatura = Fatura.objects.create(
            cartao=cartao,
            ano_referencia=2026,
            mes_referencia=11,
            data_fechamento=date(2026, 10, 25),
            data_vencimento=date(2026, 11, 5),
        )
        Parcela.objects.create(compra=privada, fatura=fatura, numero=1, valor=Decimal("80.00"))
        Parcela.objects.create(compra=compartilhada, fatura=fatura, numero=1, valor=Decimal("120.00"))

        self.client.force_login(self.kawany)
        self.ativar_espaco(ESPACO_SALA)
        response = self.client.get(reverse("cartoes:detalhe_fatura", args=[fatura.pk]))
        self.assertContains(response, "Compra da sala")
        self.assertNotContains(response, "Compra privada")
        self.assertContains(response, "total real")
        self.assertNotContains(response, "Pagar fatura")

    def test_lista_da_sala_exibe_nomes_sem_emails(self):
        self.client.force_login(self.wellington)
        response = self.client.get(reverse("salas:minha_sala"))
        self.assertContains(response, "Wellington")
        self.assertContains(response, "Kawany")
        self.assertNotContains(response, "wellington@example.com")
        self.assertNotContains(response, "kawany@example.com")
