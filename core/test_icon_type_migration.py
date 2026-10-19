from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class SeparacaoIconesMigrationTests(TransactionTestCase):
    migrate_from = [
        ("core", "0002_atualiza_icones_remove_cor"),
        ("usuarios", "0005_avatar_visual_v2"),
    ]
    migrate_to = [
        ("core", "0003_separa_icones_entrada_saida"),
        ("usuarios", "0005_avatar_visual_v2"),
    ]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        apps = executor.loader.project_state(self.migrate_from).apps
        AtalhoLancamento = apps.get_model("core", "AtalhoLancamento")
        Usuario = apps.get_model("usuarios", "Usuario")
        usuario = Usuario.objects.create(username="migracao-icones")

        self.itens_entrada = {}
        categorias = {
            "salario": "entrada_salario",
            "extra": "entrada_renda_extra",
            "segundo_emprego": "entrada_segundo_emprego",
            "fgts": "entrada_renda_extra",
            "decimo_terceiro": "entrada_decimo_terceiro",
            "vale_alimentacao": "entrada_renda_extra",
            "outros": "entrada_renda_extra",
        }
        for categoria, simbolo_esperado in categorias.items():
            item = AtalhoLancamento.objects.create(
                proprietario_usuario=usuario,
                nome=f"Entrada {categoria}",
                tipo="entrada",
                simbolo="trabalho",
                categoria=categoria,
            )
            self.itens_entrada[item.pk] = simbolo_esperado

        self.salario_pelo_nome = AtalhoLancamento.objects.create(
            proprietario_usuario=usuario,
            nome="Meu salário líquido",
            tipo="entrada",
            simbolo="trabalho",
            categoria="outros",
        )

        self.saida = AtalhoLancamento.objects.create(
            proprietario_usuario=usuario,
            nome="Saída preservada",
            tipo="saida",
            simbolo="supermercado",
            categoria="alimentacao",
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_mapeia_por_tipo_sem_alterar_os_demais_dados(self):
        AtalhoLancamento = self.apps.get_model("core", "AtalhoLancamento")

        for item_id, simbolo_esperado in self.itens_entrada.items():
            item = AtalhoLancamento.objects.get(pk=item_id)
            self.assertEqual(item.simbolo, simbolo_esperado)
            self.assertTrue(item.nome.startswith("Entrada "))

        salario = AtalhoLancamento.objects.get(pk=self.salario_pelo_nome.pk)
        self.assertEqual(salario.simbolo, "entrada_salario")

        saida = AtalhoLancamento.objects.get(pk=self.saida.pk)
        self.assertEqual(saida.simbolo, "saida_supermercado")
        self.assertEqual(saida.nome, "Saída preservada")
        self.assertEqual(saida.tipo, "saida")
        self.assertEqual(saida.categoria, "alimentacao")
