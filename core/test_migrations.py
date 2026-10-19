from datetime import date
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class PreservacaoMigracoesTests(TransactionTestCase):
    """Confere a passagem dos dados de sala para a nova propriedade opcional."""

    migrate_from = [
        ("usuarios", "0002_usuario_foto_url"),
        ("salas", "0001_initial"),
        ("contas", "0001_initial"),
        ("entradas", "0001_initial"),
        ("saidas", "0001_initial"),
        ("cartoes", "0002_mes_referencia_vencimento"),
    ]
    migrate_to = [
        ("usuarios", "0003_usuario_compartilhar_novos_lancamentos_and_more"),
        ("salas", "0002_sala_simbolo_sala_tipo"),
        ("contas", "0002_cartaocredito_autor_and_more"),
        ("entradas", "0002_remove_configuracaodizimo_configuracao_dizimo_unica_por_pessoa_tipo_and_more"),
        ("saidas", "0002_saida_autor_saida_proprietario_usuario_and_more"),
        ("cartoes", "0003_compracredito_autor_and_more"),
    ]

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        apps = self.executor.loader.project_state(self.migrate_from).apps

        Usuario = apps.get_model("usuarios", "Usuario")
        Sala = apps.get_model("salas", "Sala")
        MembroSala = apps.get_model("salas", "MembroSala")
        Conta = apps.get_model("contas", "Conta")
        Cartao = apps.get_model("contas", "CartaoCredito")
        Compra = apps.get_model("cartoes", "CompraCredito")
        Fatura = apps.get_model("cartoes", "Fatura")
        Parcela = apps.get_model("cartoes", "Parcela")
        Pagamento = apps.get_model("cartoes", "PagamentoFatura")

        usuario = Usuario.objects.create(username="historico")
        sala = Sala.objects.create(
            nome="Sala histórica",
            orcamento_mensal=Decimal("1800.00"),
            criado_por=usuario,
        )
        MembroSala.objects.create(sala=sala, usuario=usuario)
        conta = Conta.objects.create(
            sala=sala,
            tipo="dinheiro",
            nome="Conta histórica",
            titular=usuario,
            saldo_inicial=Decimal("900.00"),
            data_saldo_inicial=date(2026, 1, 1),
        )
        cartao = Cartao.objects.create(
            sala=sala,
            nome="Cartão histórico",
            titular=usuario,
            dia_fechamento=25,
            dia_vencimento=5,
        )
        compra = Compra.objects.create(
            sala=sala,
            cartao=cartao,
            responsavel=usuario,
            descricao="Compra preservada",
            valor_total=Decimal("300.00"),
            data_compra=date(2026, 9, 20),
            quantidade_parcelas=1,
            custo_vida=True,
        )
        fatura = Fatura.objects.create(
            cartao=cartao,
            ano_referencia=2026,
            mes_referencia=10,
            data_fechamento=date(2026, 9, 25),
            data_vencimento=date(2026, 10, 5),
        )
        Parcela.objects.create(
            compra=compra,
            fatura=fatura,
            numero=1,
            valor=Decimal("300.00"),
        )
        Pagamento.objects.create(
            fatura=fatura,
            conta=conta,
            valor=Decimal("300.00"),
            data_pagamento=date(2026, 10, 5),
            registrado_por=usuario,
        )
        self.ids = {
            "usuario": usuario.pk,
            "sala": sala.pk,
            "conta": conta.pk,
            "compra": compra.pk,
            "fatura": fatura.pk,
        }

        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_to)
        self.apps = self.executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        MigrationExecutor(connection).migrate(
            MigrationExecutor(connection).loader.graph.leaf_nodes()
        )
        super().tearDown()

    def test_dados_antigos_continuam_da_sala_e_pagamento_mantem_vinculos(self):
        Usuario = self.apps.get_model("usuarios", "Usuario")
        Conta = self.apps.get_model("contas", "Conta")
        Compra = self.apps.get_model("cartoes", "CompraCredito")
        Fatura = self.apps.get_model("cartoes", "Fatura")
        Sala = self.apps.get_model("salas", "Sala")

        usuario = Usuario.objects.get(pk=self.ids["usuario"])
        conta = Conta.objects.get(pk=self.ids["conta"])
        compra = Compra.objects.get(pk=self.ids["compra"])
        fatura = Fatura.objects.get(pk=self.ids["fatura"])
        sala = Sala.objects.get(pk=self.ids["sala"])

        self.assertTrue(usuario.configuracao_inicial_concluida)
        self.assertEqual(sala.tipo, "casal")
        self.assertEqual(sala.simbolo, "coracao")
        self.assertEqual(conta.sala_id, self.ids["sala"])
        self.assertIsNone(conta.proprietario_usuario_id)
        self.assertEqual(conta.saldo_inicial, Decimal("900.00"))
        self.assertEqual(compra.sala_id, self.ids["sala"])
        self.assertEqual(compra.valor_total, Decimal("300.00"))
        self.assertEqual(fatura.parcelas.get().valor, Decimal("300.00"))
        self.assertEqual(fatura.pagamento.valor, Decimal("300.00"))
        self.assertEqual(fatura.pagamento.conta_id, conta.pk)
