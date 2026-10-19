from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class MigracaoIconesItensTests(TransactionTestCase):
    migrate_from = [
        ("core", "0001_atalholancamento"),
        ("usuarios", "0005_avatar_visual_v2"),
    ]
    migrate_to = [
        ("core", "0002_atualiza_icones_remove_cor"),
        ("usuarios", "0005_avatar_visual_v2"),
    ]

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        apps = self.executor.loader.project_state(self.migrate_from).apps

        Usuario = apps.get_model("usuarios", "Usuario")
        AtalhoLancamento = apps.get_model("core", "AtalhoLancamento")
        usuario = Usuario.objects.create(username="icones-historicos")
        simbolos_antigos = [
            "generico", "casa", "alimentacao", "carteira", "entrada",
            "coracao", "moedas", "calendario", "lista",
        ]
        self.itens = {
            simbolo: AtalhoLancamento.objects.create(
                proprietario_usuario=usuario,
                nome=f"Item {simbolo}",
                tipo="saida",
                simbolo=simbolo,
                cor="azul",
                categoria="outros",
            ).pk
            for simbolo in simbolos_antigos
        }

        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_to)
        self.apps = self.executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_mapeia_simbolos_antigos_e_remove_somente_a_cor(self):
        AtalhoLancamento = self.apps.get_model("core", "AtalhoLancamento")
        mapa_esperado = {
            "generico": "financas",
            "casa": "casa",
            "alimentacao": "supermercado",
            "carteira": "banco",
            "entrada": "trabalho",
            "coracao": "hospital",
            "moedas": "poupanca",
            "calendario": "financas",
            "lista": "estudos",
        }

        for simbolo_antigo, simbolo_novo in mapa_esperado.items():
            item = AtalhoLancamento.objects.get(pk=self.itens[simbolo_antigo])
            self.assertEqual(item.simbolo, simbolo_novo)
            self.assertEqual(item.nome, f"Item {simbolo_antigo}")

        nomes_campos = {campo.name for campo in AtalhoLancamento._meta.fields}
        self.assertNotIn("cor", nomes_campos)
