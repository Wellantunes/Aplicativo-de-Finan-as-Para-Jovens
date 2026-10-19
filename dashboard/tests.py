from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.template import Context, Template
from django.urls import reverse

from cartoes.models import CompraCredito, Fatura, PagamentoFatura, Parcela
from contas.models import CartaoCredito, Conta
from entradas.models import DevolucaoDizimo, Entrada, FormaCalculoDizimo, TipoEntrada
from saidas.models import Saida
from salas.models import MembroSala, Sala

from .calculos import calcular_dashboard, periodo_do_mes
from .forms import FiltroDashboardForm


class DashboardBaseTests(TestCase):
    def setUp(self):
        Usuario = get_user_model()
        self.maria = Usuario.objects.create_user(
            username="maria",
            first_name="Maria",
            avatar_concluido=True,
            dizimo_automatico=True,
        )
        self.joao = Usuario.objects.create_user(
            username="joao",
            first_name="João",
            avatar_concluido=True,
        )
        self.sala = Sala.objects.create(
            nome="Nossa casa",
            orcamento_mensal=Decimal("2000.00"),
            controlar_dizimos=True,
            criado_por=self.maria,
        )
        MembroSala.objects.create(sala=self.sala, usuario=self.maria)
        MembroSala.objects.create(sala=self.sala, usuario=self.joao)
        sessao = self.client.session
        sessao["espaco_financeiro"] = "sala"
        sessao.save()
        self.conta_dinheiro = Conta.objects.create(
            sala=self.sala,
            tipo=Conta.Tipo.DINHEIRO,
            nome="Conta principal",
            titular=self.maria,
            saldo_inicial=Decimal("100.00"),
            data_saldo_inicial=date(2025, 9, 1),
        )
        self.conta_vale = Conta.objects.create(
            sala=self.sala,
            tipo=Conta.Tipo.VALE_ALIMENTACAO,
            nome="Vale",
            titular=self.joao,
            saldo_inicial=Decimal("0.00"),
            data_saldo_inicial=date(2025, 9, 1),
        )
        self.cartao = CartaoCredito.objects.create(
            sala=self.sala,
            nome="Cartão compartilhado",
            titular=self.maria,
            dia_fechamento=25,
            dia_vencimento=5,
        )

    def criar_entrada(
        self,
        pessoa,
        conta,
        valor,
        data_recebimento,
        tipo=TipoEntrada.SALARIO,
        dizimo=False,
    ):
        return Entrada.objects.create(
            sala=self.sala,
            pessoa=pessoa,
            tipo=tipo,
            descricao="Recebimento",
            valor=Decimal(valor),
            data=data_recebimento,
            conta_destino=conta,
            calcular_dizimo=dizimo,
            forma_calculo=(
                FormaCalculoDizimo.PERCENTUAL if dizimo else ""
            ),
            percentual_dizimo=Decimal("10.00") if dizimo else None,
        )

    def criar_saida(
        self,
        descricao,
        valor,
        responsavel,
        custo_vida,
        situacao,
        vencimento=None,
        data_pagamento=None,
        conta=None,
    ):
        return Saida.objects.create(
            sala=self.sala,
            descricao=descricao,
            valor=Decimal(valor),
            responsavel=responsavel,
            custo_vida=custo_vida,
            situacao=situacao,
            vencimento=vencimento,
            data_pagamento=data_pagamento,
            forma_pagamento=(Saida.FormaPagamento.PIX if conta else ""),
            conta=conta,
        )

    def criar_parcela(self, responsavel, valor, custo_vida=True):
        compra = CompraCredito.objects.create(
            sala=self.sala,
            cartao=self.cartao,
            responsavel=responsavel,
            descricao="Compra parcelada",
            valor_total=Decimal(valor),
            data_compra=date(2025, 9, 20),
            quantidade_parcelas=1,
            custo_vida=custo_vida,
        )
        fatura, _ = Fatura.objects.get_or_create(
            cartao=self.cartao,
            ano_referencia=2025,
            mes_referencia=10,
            defaults={
                "data_fechamento": date(2025, 9, 25),
                "data_vencimento": date(2025, 10, 5),
            },
        )
        Parcela.objects.create(
            compra=compra,
            fatura=fatura,
            numero=1,
            valor=Decimal(valor),
        )
        return fatura


class CalculoDashboardTests(DashboardBaseTests):
    def test_consultas_nao_crescem_a_cada_conta_ou_entrada(self):
        def quantidade_consultas():
            with CaptureQueriesContext(connection) as consultas:
                painel = calcular_dashboard(self.sala, 2025, 10)
                list(painel["compromissos_lista"])
            return len(consultas)

        quantidade_inicial = quantidade_consultas()

        for indice in range(8):
            conta = Conta.objects.create(
                sala=self.sala,
                tipo=Conta.Tipo.DINHEIRO,
                nome=f"Conta {indice}",
                titular=self.maria,
                saldo_inicial=Decimal("10.00"),
                data_saldo_inicial=date(2025, 9, 1),
            )
            self.criar_entrada(
                self.maria,
                conta,
                "100.00",
                date(2025, 10, 1),
                dizimo=True,
            )
            cartao = CartaoCredito.objects.create(
                sala=self.sala,
                nome=f"Cartão {indice}",
                titular=self.maria,
                dia_fechamento=25,
                dia_vencimento=5,
            )
            compra = CompraCredito.objects.create(
                sala=self.sala,
                cartao=cartao,
                responsavel=self.maria,
                descricao=f"Compra {indice}",
                valor_total=Decimal("50.00"),
                data_compra=date(2025, 9, 20),
                quantidade_parcelas=1,
                custo_vida=True,
            )
            fatura = Fatura.objects.create(
                cartao=cartao,
                ano_referencia=2025,
                mes_referencia=10,
                data_fechamento=date(2025, 9, 25),
                data_vencimento=date(2025, 10, 5),
            )
            Parcela.objects.create(
                compra=compra,
                fatura=fatura,
                numero=1,
                valor=Decimal("50.00"),
            )

        quantidade_com_varios_registros = quantidade_consultas()

        # As duas consultas agrupadas de faturas só são executadas quando há
        # alguma fatura. A quantidade não pode continuar crescendo por item.
        self.assertLessEqual(
            quantidade_com_varios_registros,
            quantidade_inicial + 2,
            "O dashboard voltou a executar consultas por conta ou entrada.",
        )

    def test_valor_principal_formata_milhar_e_sinal_antes_da_moeda(self):
        template = Template("{% load financeiro %}{{ valor|moeda_br }}")

        self.assertEqual(
            template.render(Context({"valor": Decimal("100000.00")})),
            "R$ 100.000,00",
        )
        self.assertEqual(
            template.render(Context({"valor": Decimal("-1250.90")})),
            "-R$ 1.250,90",
        )

    def test_confirmacao_mantem_lancamentos_no_mes_de_referencia(self):
        entrada = Entrada.objects.create(
            sala=self.sala,
            autor=self.maria,
            pessoa=self.maria,
            tipo=TipoEntrada.EXTRA,
            descricao="Entrada futura",
            valor=Decimal("1000.00"),
            situacao=Entrada.Situacao.A_RECEBER,
            data_prevista=date(2025, 11, 20),
            data=None,
        )
        saida = self.criar_saida(
            "Saída futura",
            "600.00",
            self.maria,
            False,
            Saida.Situacao.PENDENTE,
            vencimento=date(2025, 11, 20),
        )

        novembro = calcular_dashboard(self.sala, 2025, 11)
        outubro = calcular_dashboard(self.sala, 2025, 10)

        self.assertEqual(outubro["resultado_mes"], Decimal("0.00"))
        self.assertEqual(novembro["total_entradas_mes"], Decimal("1000.00"))
        self.assertEqual(novembro["total_saidas_mes"], Decimal("600.00"))
        self.assertEqual(novembro["resultado_mes"], Decimal("400.00"))

        entrada.situacao = Entrada.Situacao.RECEBIDA
        entrada.data = date(2025, 12, 5)
        entrada.save()
        saida.situacao = Saida.Situacao.PAGA
        saida.data_pagamento = date(2025, 12, 6)
        saida.save()

        novembro_confirmado = calcular_dashboard(self.sala, 2025, 11)
        dezembro = calcular_dashboard(self.sala, 2025, 12)

        self.assertEqual(novembro_confirmado["total_entradas_mes"], Decimal("1000.00"))
        self.assertEqual(novembro_confirmado["total_saidas_mes"], Decimal("600.00"))
        self.assertEqual(novembro_confirmado["resultado_mes"], Decimal("400.00"))
        self.assertEqual(dezembro["total_entradas_mes"], Decimal("0.00"))
        self.assertEqual(dezembro["total_saidas_mes"], Decimal("0.00"))
        self.assertEqual(dezembro["resultado_mes"], Decimal("0.00"))
        self.assertEqual(Entrada.objects.filter(pk=entrada.pk).count(), 1)
        self.assertEqual(Saida.objects.filter(pk=saida.pk).count(), 1)

        entrada.data_prevista = date(2025, 12, 20)
        entrada.save(update_fields=["data_prevista"])
        saida.vencimento = date(2025, 12, 20)
        saida.save(update_fields=["vencimento"])

        novembro_apos_edicao = calcular_dashboard(self.sala, 2025, 11)
        dezembro_apos_edicao = calcular_dashboard(self.sala, 2025, 12)

        self.assertEqual(novembro_apos_edicao["resultado_mes"], Decimal("0.00"))
        self.assertEqual(
            dezembro_apos_edicao["total_entradas_mes"], Decimal("1000.00")
        )
        self.assertEqual(
            dezembro_apos_edicao["total_saidas_mes"], Decimal("600.00")
        )
        self.assertEqual(dezembro_apos_edicao["resultado_mes"], Decimal("400.00"))

    def test_cancelados_nao_entram_no_resultado(self):
        Entrada.objects.create(
            sala=self.sala,
            autor=self.maria,
            pessoa=self.maria,
            tipo=TipoEntrada.EXTRA,
            descricao="Entrada cancelada",
            valor=Decimal("900.00"),
            situacao=Entrada.Situacao.CANCELADA,
            data_prevista=date(2025, 11, 10),
            data=None,
        )
        self.criar_saida(
            "Saída cancelada",
            "700.00",
            self.maria,
            False,
            Saida.Situacao.CANCELADA,
            vencimento=date(2025, 11, 10),
        )

        painel = calcular_dashboard(self.sala, 2025, 11)

        self.assertEqual(painel["total_entradas_mes"], Decimal("0.00"))
        self.assertEqual(painel["total_saidas_mes"], Decimal("0.00"))
        self.assertEqual(painel["resultado_mes"], Decimal("0.00"))

    def test_resultado_mensal_nao_usa_saldo_inicial_nem_transfere_entre_meses(self):
        entrada = self.criar_entrada(
            self.maria,
            None,
            "6200.00",
            date(2025, 10, 1),
        )
        saida = self.criar_saida(
            "Despesas do mÃªs",
            "6000.00",
            self.maria,
            False,
            Saida.Situacao.PAGA,
            data_pagamento=date(2025, 10, 2),
        )

        self.criar_entrada(
            self.maria,
            None,
            "3000.00",
            date(2025, 11, 1),
        )
        self.criar_saida(
            "Despesas de novembro",
            "3500.00",
            self.maria,
            False,
            Saida.Situacao.PENDENTE,
            vencimento=date(2025, 11, 20),
        )

        outubro = calcular_dashboard(self.sala, 2025, 10)
        novembro = calcular_dashboard(self.sala, 2025, 11)

        self.assertEqual(outubro["total_entradas_mes"], Decimal("6200.00"))
        self.assertEqual(outubro["total_saidas_mes"], Decimal("6000.00"))
        self.assertEqual(outubro["resultado_mes"], Decimal("200.00"))
        self.assertFalse(outubro["mes_em_deficit"])
        self.assertEqual(novembro["total_entradas_mes"], Decimal("3000.00"))
        self.assertEqual(novembro["total_saidas_mes"], Decimal("3500.00"))
        self.assertEqual(novembro["resultado_mes"], Decimal("-500.00"))
        self.assertTrue(novembro["mes_em_deficit"])

        entrada.valor = Decimal("6100.00")
        entrada.save(update_fields=["valor"])
        saida.delete()
        outubro_corrigido = calcular_dashboard(self.sala, 2025, 10)

        self.assertEqual(outubro_corrigido["total_entradas_mes"], Decimal("6100.00"))
        self.assertEqual(outubro_corrigido["total_saidas_mes"], Decimal("0.00"))
        self.assertEqual(outubro_corrigido["resultado_mes"], Decimal("6100.00"))

    def test_pendencia_entra_no_resultado_e_deficit_fica_explicito(self):
        self.criar_entrada(
            self.maria,
            None,
            "500.00",
            date(2025, 10, 1),
        )
        self.criar_saida(
            "Conta paga",
            "700.00",
            self.maria,
            False,
            Saida.Situacao.PAGA,
            data_pagamento=date(2025, 10, 2),
        )
        self.criar_saida(
            "Conta prevista",
            "900.00",
            self.maria,
            False,
            Saida.Situacao.PENDENTE,
            vencimento=date(2025, 10, 20),
        )

        painel = calcular_dashboard(self.sala, 2025, 10)

        self.assertEqual(painel["total_saidas_mes"], Decimal("1600.00"))
        self.assertEqual(painel["resultado_mes"], Decimal("-1100.00"))
        self.assertTrue(painel["mes_em_deficit"])

    def test_calcula_indicadores_sem_duplicar_parcelas_com_pagamento(self):
        salario = self.criar_entrada(
            self.maria,
            self.conta_dinheiro,
            "3000.00",
            date(2025, 10, 1),
            dizimo=True,
        )
        self.criar_entrada(
            self.joao,
            self.conta_vale,
            "630.00",
            date(2025, 10, 2),
            tipo=TipoEntrada.VALE_ALIMENTACAO,
        )
        DevolucaoDizimo.objects.create(
            entrada=salario,
            valor=Decimal("200.00"),
            data=date(2025, 10, 20),
            conta=self.conta_dinheiro,
            registrado_por=self.maria,
        )
        self.criar_saida(
            "Aluguel",
            "900.00",
            self.maria,
            True,
            Saida.Situacao.PENDENTE,
            vencimento=date(2025, 10, 10),
        )
        self.criar_saida(
            "Mercado",
            "150.00",
            self.joao,
            True,
            Saida.Situacao.PAGA,
            data_pagamento=date(2025, 10, 12),
            conta=self.conta_vale,
        )
        self.criar_saida(
            "Telefone",
            "80.00",
            self.maria,
            False,
            Saida.Situacao.PAGA,
            data_pagamento=date(2025, 10, 13),
            conta=self.conta_dinheiro,
        )
        fatura = self.criar_parcela(self.joao, "300.00", custo_vida=True)
        self.criar_parcela(self.maria, "120.00", custo_vida=False)
        PagamentoFatura.objects.create(
            fatura=fatura,
            conta=self.conta_dinheiro,
            valor=Decimal("420.00"),
            data_pagamento=date(2025, 10, 25),
            registrado_por=self.maria,
        )

        painel = calcular_dashboard(self.sala, 2025, 10)

        self.assertEqual(painel["entradas_dinheiro"], Decimal("3000.00"))
        self.assertEqual(painel["vale_mes"], Decimal("630.00"))
        self.assertEqual(painel["dizimo_previsto"], Decimal("300.00"))
        self.assertEqual(painel["dizimo_devolvido"], Decimal("200.00"))
        self.assertEqual(painel["dizimo_pendente"], Decimal("100.00"))
        self.assertEqual(painel["custo_vida"], Decimal("1350.00"))
        self.assertEqual(painel["outros_gastos"], Decimal("200.00"))
        self.assertEqual(painel["total_entradas_mes"], Decimal("3630.00"))
        self.assertEqual(painel["saidas_vale_mes"], Decimal("150.00"))
        self.assertEqual(painel["total_saidas_mes"], Decimal("1600.00"))
        self.assertEqual(painel["resultado_mes"], Decimal("1400.00"))
        self.assertEqual(painel["saidas_dinheiro"], Decimal("700.00"))
        self.assertEqual(painel["saldo_dinheiro"], Decimal("2400.00"))
        self.assertEqual(painel["saldo_vale"], Decimal("480.00"))
        self.assertEqual(painel["compromissos_dinheiro"], Decimal("1000.00"))
        self.assertEqual(
            painel["disponivel_apos_compromissos"],
            Decimal("1400.00"),
        )
        self.assertEqual(painel["orcamento_restante"], Decimal("650.00"))

    def test_total_de_entradas_inclui_vale_sem_alterar_resultado_em_dinheiro(self):
        self.criar_entrada(
            self.maria,
            self.conta_dinheiro,
            "2700.00",
            date(2025, 10, 5),
        )
        vale = self.criar_entrada(
            self.maria,
            self.conta_vale,
            "280.00",
            date(2025, 10, 6),
            tipo=TipoEntrada.VALE_ALIMENTACAO,
        )

        painel = calcular_dashboard(self.sala, 2025, 10)
        self.assertEqual(painel["entradas_dinheiro"], Decimal("2700.00"))
        self.assertEqual(painel["vale_mes"], Decimal("280.00"))
        self.assertEqual(painel["total_entradas_mes"], Decimal("2980.00"))
        self.assertEqual(painel["resultado_mes"], Decimal("2700.00"))

        vale.valor = Decimal("300.00")
        vale.full_clean()
        vale.save()
        painel_editado = calcular_dashboard(self.sala, 2025, 10)
        self.assertEqual(painel_editado["total_entradas_mes"], Decimal("3000.00"))
        self.assertEqual(painel_editado["resultado_mes"], Decimal("2700.00"))

        vale.situacao = Entrada.Situacao.CANCELADA
        vale.full_clean()
        vale.save()
        painel_cancelado = calcular_dashboard(self.sala, 2025, 10)
        self.assertEqual(painel_cancelado["total_entradas_mes"], Decimal("2700.00"))
        self.assertEqual(painel_cancelado["vale_mes"], Decimal("0.00"))

        vale.delete()
        painel_excluido = calcular_dashboard(self.sala, 2025, 10)
        self.assertEqual(painel_excluido["total_entradas_mes"], Decimal("2700.00"))
        self.assertEqual(painel_excluido["resultado_mes"], Decimal("2700.00"))

    def test_fechamento_historico_ignora_pagamento_feito_depois_do_mes(self):
        self.criar_entrada(
            self.maria,
            self.conta_dinheiro,
            "500.00",
            date(2025, 10, 1),
        )
        fatura = self.criar_parcela(self.maria, "200.00")
        PagamentoFatura.objects.create(
            fatura=fatura,
            conta=self.conta_dinheiro,
            valor=Decimal("200.00"),
            data_pagamento=date(2025, 11, 2),
            registrado_por=self.maria,
        )

        outubro = calcular_dashboard(self.sala, 2025, 10)
        novembro = calcular_dashboard(self.sala, 2025, 11)

        self.assertEqual(outubro["tipo_periodo"], "fechamento")
        self.assertEqual(outubro["saldo_dinheiro"], Decimal("600.00"))
        self.assertEqual(outubro["compromissos_faturas"], Decimal("200.00"))
        self.assertEqual(novembro["saldo_dinheiro"], Decimal("400.00"))
        self.assertEqual(novembro["saidas_dinheiro"], Decimal("200.00"))

    def test_filtro_individual_atribui_parcela_ao_responsavel_da_compra(self):
        fatura = self.criar_parcela(self.joao, "300.00", custo_vida=True)
        self.criar_parcela(self.maria, "120.00", custo_vida=False)
        PagamentoFatura.objects.create(
            fatura=fatura,
            conta=self.conta_dinheiro,
            valor=Decimal("420.00"),
            data_pagamento=date(2025, 10, 25),
            registrado_por=self.maria,
        )

        painel_joao = calcular_dashboard(self.sala, 2025, 10, self.joao)
        painel_maria = calcular_dashboard(self.sala, 2025, 10, self.maria)

        self.assertEqual(painel_joao["custo_vida"], Decimal("300.00"))
        self.assertEqual(painel_joao["outros_gastos"], Decimal("0.00"))
        self.assertEqual(painel_joao["saidas_dinheiro"], Decimal("300.00"))
        self.assertEqual(painel_maria["custo_vida"], Decimal("0.00"))
        self.assertEqual(painel_maria["outros_gastos"], Decimal("120.00"))
        self.assertEqual(painel_maria["saidas_dinheiro"], Decimal("120.00"))

    def test_compromissos_incluem_atrasados_e_excluem_mes_seguinte(self):
        self.criar_saida(
            "Conta atrasada",
            "90.00",
            self.maria,
            False,
            Saida.Situacao.PENDENTE,
            vencimento=date(2025, 9, 20),
        )
        self.criar_saida(
            "Conta de outubro",
            "110.00",
            self.maria,
            False,
            Saida.Situacao.PENDENTE,
            vencimento=date(2025, 10, 30),
        )
        self.criar_saida(
            "Conta de novembro",
            "300.00",
            self.maria,
            False,
            Saida.Situacao.PENDENTE,
            vencimento=date(2025, 11, 1),
        )

        painel = calcular_dashboard(self.sala, 2025, 10)

        self.assertEqual(painel["compromissos_saidas"], Decimal("200.00"))
        descricoes = list(
            painel["compromissos_lista"].values_list("descricao", flat=True)
        )
        self.assertIn("Conta atrasada", descricoes)
        self.assertIn("Conta de outubro", descricoes)
        self.assertNotIn("Conta de novembro", descricoes)

    def test_periodo_atual_usa_hoje_e_futuro_e_identificado_como_previsao(self):
        with patch("dashboard.calculos.timezone.localdate", return_value=date(2026, 10, 9)):
            _, _, referencia_atual, tipo_atual = periodo_do_mes(2026, 10)
            _, _, referencia_futura, tipo_futuro = periodo_do_mes(2026, 11)

        self.assertEqual(referencia_atual, date(2026, 10, 9))
        self.assertEqual(tipo_atual, "atual")
        self.assertEqual(referencia_futura, date(2026, 11, 30))
        self.assertEqual(tipo_futuro, "previsao")


class DashboardViewTests(DashboardBaseTests):
    def test_exige_login(self):
        response = self.client.get(reverse("dashboard:mensal"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("account_login"), response.url)

    def test_mostra_painel_mobile_com_filtro_e_atalhos(self):
        self.client.force_login(self.maria)

        response = self.client.get(
            reverse("dashboard:mensal"),
            {"mes": "2025-10"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="viewport"')
        self.assertContains(response, "Painel mensal")
        self.assertContains(response, "Todos")
        destino_entrada = reverse("core:lancamentos") + "?tipo=entrada&amp;mes=2025-10"
        destino_saida = reverse("core:lancamentos") + "?tipo=saida&amp;mes=2025-10"
        self.assertContains(response, f'href="{destino_entrada}"')
        self.assertContains(response, f'href="{destino_saida}"')
        self.assertNotContains(response, f'href="{reverse("entradas:criar")}"')
        self.assertNotContains(response, f'href="{reverse("saidas:criar")}"')

    def test_painel_individual_usa_composicao_compacta_sem_filtro_de_responsavel(self):
        sessao = self.client.session
        sessao["espaco_financeiro"] = "individual"
        sessao.save()
        self.client.force_login(self.maria)

        response = self.client.get(
            reverse("dashboard:mensal"),
            {"mes": "2025-10"},
        )

        self.assertContains(response, 'class="dd-dashboard dashboard"')
        self.assertContains(response, "Meu espaço")
        self.assertContains(response, "Nossa sala")
        self.assertContains(response, "dashboard-individual.css")
        self.assertContains(response, "dropduo/icons/moedas-empilhadas.png")
        self.assertContains(response, "dropduo/icons/seta-entrada.png")
        self.assertContains(response, "dropduo/scenes/planta-vaso.png")
        self.assertContains(response, 'class="dd-avatar-link"')
        self.assertContains(response, 'aria-label="Editar meu avatar"')
        self.assertNotContains(response, "dropduo/scenes/moldura-foto.png")
        self.assertNotContains(response, "room-scene.svg")
        self.assertNotContains(response, 'name="responsavel"')
        self.assertNotContains(response, "Atualizar painel")
        self.assertContains(response, "dropduo/icons/bau.png")
        self.assertNotContains(response, "dropduo/scenes/cacto.png")
        self.assertNotContains(response, "dropduo/scenes/areia.png")
        self.assertNotContains(response, "dropduo/scenes/nuvem.png")
        self.assertNotContains(response, "dropduo/icons/calendario.png")
        self.assertContains(response, 'class="month-bar"')
        self.assertContains(response, 'aria-label="Mês anterior"')
        self.assertContains(response, 'aria-label="Próximo mês"')
        self.assertContains(response, "Resultado do mês")
        self.assertContains(response, "Entradas do mês")
        self.assertContains(response, "Saídas do mês")
        self.assertNotContains(response, "Dinheiro: R$ 0,00 · Vale: R$ 0,00")
        self.assertContains(
            response,
            "Entradas em dinheiro menos saídas em dinheiro. O vale-alimentação é acompanhado separadamente.",
        )
        self.assertNotContains(response, "Previsão do mês")
        self.assertNotContains(response, "Sobra do mês")
        self.assertContains(response, f'href="{reverse("entradas:lista")}?mes=2025-10"')
        self.assertContains(
            response,
            f'href="{reverse("entradas:lista")}?mes=2025-10#dizimos"',
        )
        self.assertContains(
            response,
            f'href="{reverse("saidas:lista")}?mes=2025-10&amp;custo_vida=1#titulo-custo-vida"',
        )
        self.assertContains(
            response,
            f'href="{reverse("core:registrar_vale")}?mes=2025-10"',
        )
        self.assertContains(response, f'href="{reverse("saidas:lista")}?mes=2025-10"')

    def test_cards_preservam_mes_e_responsavel_no_espaco_compartilhado(self):
        self.client.force_login(self.maria)

        response = self.client.get(
            reverse("dashboard:mensal"),
            {"mes": "2025-10", "responsavel": f"usuario:{self.joao.pk}"},
        )

        self.assertContains(
            response,
            f'{reverse("entradas:lista")}?mes=2025-10&amp;pessoa={self.joao.pk}',
        )
        self.assertContains(
            response,
            f'{reverse("saidas:lista")}?mes=2025-10&amp;responsavel={self.joao.pk}',
        )
        self.assertContains(response, "Entradas do mês")
        self.assertContains(response, "Saídas do mês")
        self.assertNotContains(response, "Dinheiro: R$ 0,00 · Vale: R$ 0,00")

    def test_setas_mensais_tratam_virada_do_ano(self):
        self.client.force_login(self.maria)

        response = self.client.get(
            reverse("dashboard:mensal"),
            {"mes": "2026-01"},
        )

        self.assertContains(response, "?mes=2025-12")
        self.assertContains(response, "?mes=2026-02")

    def test_setas_mensais_preservam_filtro_por_responsavel(self):
        self.client.force_login(self.maria)
        responsavel = f"usuario:{self.joao.pk}"

        response = self.client.get(
            reverse("dashboard:mensal"),
            {"mes": "2026-12", "responsavel": responsavel},
        )

        self.assertContains(
            response,
            f"?mes=2026-11&amp;responsavel=usuario%3A{self.joao.pk}",
        )
        self.assertContains(
            response,
            f"?mes=2027-01&amp;responsavel=usuario%3A{self.joao.pk}",
        )

    def test_sala_de_amigos_usa_linguagem_de_grupo_e_simbolo_bau(self):
        self.sala.tipo = Sala.Tipo.AMIGOS
        self.sala.simbolo = Sala.Simbolo.BAU
        self.sala.save(update_fields=["tipo", "simbolo"])
        self.client.force_login(self.maria)

        response = self.client.get(
            reverse("dashboard:mensal"),
            {"mes": "2025-10"},
        )

        self.assertContains(response, "Resultado do mês")
        self.assertNotContains(response, "Disponível do grupo")

    def test_responsavel_de_outra_sala_nao_e_aceito_no_filtro(self):
        Usuario = get_user_model()
        externo = Usuario.objects.create_user(username="externo", avatar_concluido=True)
        outra_sala = Sala.objects.create(
            nome="Outra sala",
            orcamento_mensal=Decimal("500.00"),
            criado_por=externo,
        )
        MembroSala.objects.create(sala=outra_sala, usuario=externo)

        formulario = FiltroDashboardForm(
            {"mes": "2025-10", "responsavel": externo.pk},
            sala=self.sala,
        )

        self.assertFalse(formulario.is_valid())
        self.assertIn("responsavel", formulario.errors)

    def test_usuario_externo_ve_apenas_os_dados_da_propria_sala(self):
        Usuario = get_user_model()
        externo = Usuario.objects.create_user(username="externo", avatar_concluido=True)
        outra_sala = Sala.objects.create(
            nome="Outra sala",
            orcamento_mensal=Decimal("500.00"),
            criado_por=externo,
        )
        MembroSala.objects.create(sala=outra_sala, usuario=externo)
        self.client.force_login(externo)

        response = self.client.get(
            reverse("dashboard:mensal"),
            {"mes": "2025-10"},
        )

        self.assertContains(response, "Outra sala")
        self.assertNotContains(response, "Nossa casa")

    def test_dizimos_individuais_desativados_somem_sem_apagar_historico(self):
        self.maria.dizimo_automatico = False
        self.maria.save(update_fields=["dizimo_automatico"])
        entrada = Entrada.objects.create(
            proprietario_usuario=self.maria,
            autor=self.maria,
            pessoa=self.maria,
            tipo=TipoEntrada.SALARIO,
            descricao="Histórico preservado",
            valor=Decimal("1000.00"),
            data=date(2025, 10, 1),
            conta_destino=Conta.objects.create(
                proprietario_usuario=self.maria,
                autor=self.maria,
                titular=self.maria,
                tipo=Conta.Tipo.DINHEIRO,
                nome="Individual",
                saldo_inicial=Decimal("0.00"),
                data_saldo_inicial=date(2025, 1, 1),
            ),
            calcular_dizimo=True,
            forma_calculo=FormaCalculoDizimo.PERCENTUAL,
            percentual_dizimo=Decimal("10.00"),
        )
        sessao = self.client.session
        sessao["espaco_financeiro"] = "individual"
        sessao.save()
        self.client.force_login(self.maria)

        response = self.client.get(reverse("dashboard:mensal"), {"mes": "2025-10"})

        self.assertNotContains(response, "Dízimos previstos")
        self.assertNotContains(response, "Dízimos pendentes")
        self.assertTrue(Entrada.objects.filter(pk=entrada.pk, dizimo_previsto=Decimal("100.00")).exists())
        painel = calcular_dashboard(None, 2025, 10, usuario=self.maria)
        self.assertFalse(painel["controla_dizimos"])
        self.assertEqual(painel["compromissos_dizimo"], Decimal("0.00"))

    def test_preferencia_da_sala_independe_da_preferencia_individual(self):
        self.maria.dizimo_automatico = False
        self.maria.save(update_fields=["dizimo_automatico"])
        self.client.force_login(self.maria)

        response_sala_ativa = self.client.get(reverse("dashboard:mensal"), {"mes": "2025-10"})
        self.assertContains(response_sala_ativa, "Dízimos previstos")

        self.sala.controlar_dizimos = False
        self.sala.save(update_fields=["controlar_dizimos"])
        self.maria.dizimo_automatico = True
        self.maria.save(update_fields=["dizimo_automatico"])
        response_sala_desativada = self.client.get(reverse("dashboard:mensal"), {"mes": "2025-10"})
        self.assertNotContains(response_sala_desativada, "Dízimos previstos")
