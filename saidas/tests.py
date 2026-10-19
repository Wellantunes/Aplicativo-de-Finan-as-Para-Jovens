import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse

from contas.models import Conta
from entradas.models import DevolucaoDizimo, Entrada, FormaCalculoDizimo, TipoEntrada
from salas.models import MembroSala, Sala

from .models import Saida
from .services import criar_saida, marcar_saida_como_paga


class FluxoSaidasTests(TestCase):
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
        self.conta_dinheiro = Conta.objects.create(
            sala=self.sala,
            tipo=Conta.Tipo.DINHEIRO,
            nome="Conta principal",
            titular=self.criador,
            saldo_inicial=Decimal("2900.00"),
            data_saldo_inicial=date(2026, 10, 1),
        )
        self.outra_conta = Conta.objects.create(
            sala=self.sala,
            tipo=Conta.Tipo.DINHEIRO,
            nome="Carteira",
            titular=self.parceira,
            saldo_inicial=Decimal("100.00"),
            data_saldo_inicial=date(2026, 10, 1),
        )
        self.conta_vale = Conta.objects.create(
            sala=self.sala,
            tipo=Conta.Tipo.VALE_ALIMENTACAO,
            nome="Vale mercado",
            titular=self.parceira,
            saldo_inicial=Decimal("630.00"),
            data_saldo_inicial=date(2026, 10, 1),
        )

        self.sala_externa = Sala.objects.create(
            nome="Outra sala",
            orcamento_mensal=Decimal("1000.00"),
            criado_por=self.externo,
        )
        MembroSala.objects.create(sala=self.sala_externa, usuario=self.externo)
        sessao = self.client.session
        sessao["espaco_financeiro"] = "sala"
        sessao.save()
        self.conta_externa = Conta.objects.create(
            sala=self.sala_externa,
            tipo=Conta.Tipo.DINHEIRO,
            nome="Conta externa",
            titular=self.externo,
            saldo_inicial=Decimal("500.00"),
            data_saldo_inicial=date(2026, 10, 1),
        )

    def dados_formulario(self, **alteracoes):
        dados = {
            "descricao": "Aluguel",
            "valor": "900.00",
            "responsavel": self.criador.pk,
            "custo_vida": "on",
            "situacao": Saida.Situacao.PENDENTE,
            "vencimento": "2026-10-10",
            "data_pagamento": "",
            "forma_pagamento": "",
            "conta": "",
            "chave_formulario": str(uuid.uuid4()),
        }
        dados.update(alteracoes)
        return dados

    def criar_pendente(self, **alteracoes):
        dados = {
            "descricao": "Aluguel",
            "valor": Decimal("900.00"),
            "responsavel": self.criador,
            "custo_vida": True,
            "situacao": Saida.Situacao.PENDENTE,
            "vencimento": date(2026, 10, 10),
            "data_pagamento": None,
            "forma_pagamento": "",
            "conta": None,
        }
        dados.update(alteracoes)
        saida, _ = criar_saida(self.sala, uuid.uuid4(), dados)
        return saida

    def criar_paga(self, **alteracoes):
        dados = {
            "descricao": "Mercado",
            "valor": Decimal("150.00"),
            "responsavel": self.parceira,
            "custo_vida": True,
            "situacao": Saida.Situacao.PAGA,
            "vencimento": None,
            "data_pagamento": date(2026, 10, 8),
            "forma_pagamento": Saida.FormaPagamento.VALE_ALIMENTACAO,
            "conta": self.conta_vale,
        }
        dados.update(alteracoes)
        saida, _ = criar_saida(self.sala, uuid.uuid4(), dados)
        return saida

    def test_paginas_exigem_login(self):
        self.assertEqual(self.client.get(reverse("saidas:lista")).status_code, 302)
        self.assertEqual(self.client.get(reverse("saidas:criar")).status_code, 302)

    def test_exemplo_completo_produz_saldos_corretos(self):
        aluguel = self.criar_pendente()
        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("2900.00"))

        self.criar_paga()
        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("2900.00"))
        self.assertEqual(self.conta_vale.saldo_atual, Decimal("480.00"))

        marcar_saida_como_paga(
            aluguel,
            date(2026, 10, 10),
            Saida.FormaPagamento.PIX,
            self.conta_dinheiro,
        )
        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("2000.00"))

        self.client.force_login(self.parceira)
        response = self.client.post(
            reverse("saidas:editar", args=[aluguel.pk]),
            self.dados_formulario(
                valor="850.00",
                situacao=Saida.Situacao.PAGA,
                vencimento="2026-10-10",
                data_pagamento="2026-10-10",
                forma_pagamento=Saida.FormaPagamento.PIX,
                conta=self.conta_dinheiro.pk,
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("2050.00"))
        self.assertEqual(self.conta_vale.saldo_atual, Decimal("480.00"))

    def test_pendente_nao_reduz_saldo(self):
        self.criar_pendente()

        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("2900.00"))

    def test_voltar_de_paga_para_pendente_devolve_valor_ao_saldo(self):
        saida = self.criar_paga(
            valor=Decimal("300.00"),
            forma_pagamento=Saida.FormaPagamento.PIX,
            conta=self.conta_dinheiro,
        )
        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("2600.00"))
        self.client.force_login(self.criador)

        response = self.client.post(
            reverse("saidas:editar", args=[saida.pk]),
            self.dados_formulario(
                descricao=saida.descricao,
                valor="300.00",
                situacao=Saida.Situacao.PENDENTE,
                vencimento="2026-11-10",
                data_pagamento="2026-10-08",
                forma_pagamento=Saida.FormaPagamento.PIX,
                conta=self.conta_dinheiro.pk,
            ),
        )

        self.assertEqual(response.status_code, 302)
        saida.refresh_from_db()
        self.assertEqual(saida.situacao, Saida.Situacao.PENDENTE)
        self.assertIsNone(saida.conta)
        self.assertIsNone(saida.data_pagamento)
        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("2900.00"))

    def test_editar_saida_preserva_vinculo_historico_com_conta(self):
        saida = self.criar_paga(
            valor=Decimal("80.00"),
            forma_pagamento=Saida.FormaPagamento.DINHEIRO,
            conta=self.conta_dinheiro,
        )
        self.client.force_login(self.parceira)

        response = self.client.post(
            reverse("saidas:editar", args=[saida.pk]),
            self.dados_formulario(
                descricao=saida.descricao,
                valor="80.00",
                situacao=Saida.Situacao.PAGA,
                data_pagamento="2026-10-08",
                forma_pagamento=Saida.FormaPagamento.DINHEIRO,
                conta=self.outra_conta.pk,
            ),
        )

        self.assertEqual(response.status_code, 302)
        saida.refresh_from_db()
        self.assertEqual(saida.conta, self.conta_dinheiro)
        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("2820.00"))
        self.assertEqual(self.outra_conta.saldo_atual, Decimal("100.00"))

    def test_excluir_saida_paga_reverte_desconto(self):
        saida = self.criar_paga(
            valor=Decimal("200.00"),
            forma_pagamento=Saida.FormaPagamento.DEBITO,
            conta=self.conta_dinheiro,
        )
        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("2700.00"))
        self.client.force_login(self.criador)

        response = self.client.post(reverse("saidas:excluir", args=[saida.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Saida.objects.filter(pk=saida.pk).exists())
        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("2900.00"))

    def test_marcar_como_paga_nao_exige_conta(self):
        saida = self.criar_pendente(valor=Decimal("3000.00"))
        self.client.force_login(self.criador)

        response = self.client.post(
            reverse("saidas:pagar", args=[saida.pk]),
            {
                "data_pagamento": "2026-10-10",
                "forma_pagamento": Saida.FormaPagamento.PIX,
                "conta": self.conta_dinheiro.pk,
            },
            follow=True,
        )

        saida.refresh_from_db()
        self.assertEqual(saida.situacao, Saida.Situacao.PAGA)
        self.assertIsNone(saida.conta)
        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("2900.00"))

    def test_dados_de_conta_postados_sao_ignorados_no_fluxo_comum(self):
        self.client.force_login(self.criador)

        resposta_pix = self.client.post(
            reverse("saidas:criar"),
            self.dados_formulario(
                situacao=Saida.Situacao.PAGA,
                data_pagamento="2026-10-10",
                forma_pagamento=Saida.FormaPagamento.PIX,
                conta=self.conta_vale.pk,
            ),
        )
        resposta_vale = self.client.post(
            reverse("saidas:criar"),
            self.dados_formulario(
                situacao=Saida.Situacao.PAGA,
                data_pagamento="2026-10-10",
                forma_pagamento=Saida.FormaPagamento.VALE_ALIMENTACAO,
                conta=self.conta_dinheiro.pk,
            ),
        )

        self.assertEqual(resposta_pix.status_code, 302)
        self.assertEqual(resposta_vale.status_code, 302)
        self.assertEqual(Saida.objects.count(), 2)
        self.assertFalse(Saida.objects.filter(conta__isnull=False).exists())

    def test_datas_obrigatorias_dependem_da_situacao(self):
        self.client.force_login(self.criador)

        pendente_sem_vencimento = self.client.post(
            reverse("saidas:criar"),
            self.dados_formulario(vencimento=""),
        )
        paga_sem_data = self.client.post(
            reverse("saidas:criar"),
            self.dados_formulario(
                situacao=Saida.Situacao.PAGA,
                vencimento="",
                data_pagamento="",
                forma_pagamento=Saida.FormaPagamento.PIX,
                conta=self.conta_dinheiro.pk,
            ),
        )

        self.assertContains(pendente_sem_vencimento, "Informe o vencimento")
        self.assertContains(paga_sem_data, "Informe a data do pagamento")
        self.assertFalse(Saida.objects.exists())

    def test_reenvio_nao_duplica_saida(self):
        self.client.force_login(self.criador)
        dados = self.dados_formulario(
            situacao=Saida.Situacao.PAGA,
            data_pagamento="2026-10-10",
            forma_pagamento=Saida.FormaPagamento.PIX,
            conta=self.conta_dinheiro.pk,
        )

        primeira = self.client.post(reverse("saidas:criar"), dados)
        segunda = self.client.post(reverse("saidas:criar"), dados)

        self.assertEqual(primeira.status_code, 302)
        self.assertEqual(segunda.status_code, 302)
        self.assertEqual(Saida.objects.count(), 1)
        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("2900.00"))

    def test_reenvio_do_pagamento_desconta_uma_unica_vez(self):
        saida = self.criar_pendente(valor=Decimal("500.00"))
        self.client.force_login(self.parceira)
        dados = {
            "data_pagamento": "2026-10-10",
            "forma_pagamento": Saida.FormaPagamento.PIX,
            "conta": self.conta_dinheiro.pk,
        }

        primeira = self.client.post(reverse("saidas:pagar", args=[saida.pk]), dados)
        segunda = self.client.post(reverse("saidas:pagar", args=[saida.pk]), dados)

        self.assertEqual(primeira.status_code, 302)
        self.assertEqual(segunda.status_code, 302)
        self.assertEqual(Saida.objects.count(), 1)
        saida.refresh_from_db()
        self.assertIsNone(saida.conta)
        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("2900.00"))

    def test_filtro_mensal_usa_vencimento_mesmo_depois_do_pagamento(self):
        paga_setembro = self.criar_paga(
            descricao="Paga em outubro com referência em setembro",
            vencimento=date(2026, 9, 20),
            data_pagamento=date(2026, 10, 2),
        )
        pendente_outubro = self.criar_pendente(
            descricao="Pendente em outubro",
            vencimento=date(2026, 10, 25),
        )
        self.criar_pendente(
            descricao="Pendente em novembro",
            vencimento=date(2026, 11, 5),
        )
        self.client.force_login(self.criador)

        outubro = self.client.get(reverse("saidas:lista"), {"mes": "2026-10"})
        setembro = self.client.get(reverse("saidas:lista"), {"mes": "2026-09"})

        self.assertNotContains(outubro, paga_setembro.descricao)
        self.assertContains(outubro, pendente_outubro.descricao)
        self.assertNotContains(outubro, "Pendente em novembro")
        self.assertContains(setembro, paga_setembro.descricao)

    def test_custo_de_vida_abre_mes_sem_filtros_visiveis(self):
        self.criar_pendente(
            descricao="Aluguel de outubro",
            vencimento=date(2026, 10, 10),
            custo_vida=True,
        )
        self.client.force_login(self.criador)

        response = self.client.get(
            reverse("saidas:lista"),
            {"mes": "2026-10", "custo_vida": "1"},
        )

        self.assertContains(response, "Aluguel de outubro")
        self.assertNotContains(response, 'id="titulo-filtros"')
        self.assertNotContains(response, "Gerar relatório")
        self.assertContains(response, self.sala.nome)
        self.assertContains(
            response,
            f'{reverse("core:lancamentos")}?tipo=saida&amp;mes=2026-10',
        )
        self.assertNotContains(response, reverse("saidas:criar"))

    def test_filtros_por_responsavel_e_situacao(self):
        self.criar_pendente(descricao="Conta do João", responsavel=self.criador)
        self.criar_pendente(descricao="Conta da Maria", responsavel=self.parceira)
        self.criar_paga(descricao="Mercado pago", responsavel=self.parceira)
        self.client.force_login(self.criador)

        response = self.client.get(
            reverse("saidas:lista"),
            {
                "responsavel": self.parceira.pk,
                "situacao": Saida.Situacao.PENDENTE,
            },
        )

        self.assertContains(response, "Conta da Maria")
        self.assertNotContains(response, "Conta do João")
        self.assertNotContains(response, "Mercado pago")

    def test_custo_de_vida_separa_pago_e_pendente(self):
        self.criar_pendente(valor=Decimal("900.00"), custo_vida=True)
        self.criar_paga(valor=Decimal("150.00"), custo_vida=True)
        self.criar_paga(
            descricao="Não é custo",
            valor=Decimal("50.00"),
            custo_vida=False,
        )
        self.client.force_login(self.criador)

        response = self.client.get(reverse("saidas:lista"), {"mes": "2026-10"})

        self.assertEqual(response.context["total_custo_pago"], Decimal("150.00"))
        self.assertEqual(response.context["total_custo_pendente"], Decimal("900.00"))

    def test_devolucao_de_dizimo_continua_contabilizada_uma_vez(self):
        entrada = Entrada.objects.create(
            sala=self.sala,
            pessoa=self.criador,
            tipo=TipoEntrada.SALARIO,
            descricao="Salário",
            valor=Decimal("1000.00"),
            data=date(2026, 10, 1),
            conta_destino=self.conta_dinheiro,
            calcular_dizimo=True,
            forma_calculo=FormaCalculoDizimo.PERCENTUAL,
            percentual_dizimo=Decimal("10"),
        )
        DevolucaoDizimo.objects.create(
            entrada=entrada,
            valor=Decimal("100.00"),
            data=date(2026, 10, 2),
            conta=self.conta_dinheiro,
            registrado_por=self.criador,
        )
        self.criar_paga(
            valor=Decimal("200.00"),
            forma_pagamento=Saida.FormaPagamento.PIX,
            conta=self.conta_dinheiro,
        )

        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("3600.00"))

    def test_os_dois_membros_podem_administrar_saidas(self):
        self.client.force_login(self.parceira)

        response = self.client.post(
            reverse("saidas:criar"),
            self.dados_formulario(responsavel=self.parceira.pk),
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Saida.objects.filter(responsavel=self.parceira).exists())

    def test_usuario_externo_nao_consulta_nem_altera_saida(self):
        saida = self.criar_pendente()
        self.client.force_login(self.externo)

        resposta_lista = self.client.get(reverse("saidas:lista"))
        resposta_editar = self.client.get(reverse("saidas:editar", args=[saida.pk]))
        resposta_excluir = self.client.post(reverse("saidas:excluir", args=[saida.pk]))
        resposta_pagar = self.client.get(reverse("saidas:pagar", args=[saida.pk]))

        self.assertNotContains(resposta_lista, saida.descricao)
        self.assertEqual(resposta_editar.status_code, 404)
        self.assertEqual(resposta_excluir.status_code, 404)
        self.assertEqual(resposta_pagar.status_code, 404)

    def test_responsavel_externo_e_recusado_e_conta_postada_e_ignorada(self):
        self.client.force_login(self.criador)

        resposta_responsavel = self.client.post(
            reverse("saidas:criar"),
            self.dados_formulario(responsavel=self.externo.pk),
        )
        resposta_conta = self.client.post(
            reverse("saidas:criar"),
            self.dados_formulario(
                situacao=Saida.Situacao.PAGA,
                data_pagamento="2026-10-10",
                forma_pagamento=Saida.FormaPagamento.PIX,
                conta=self.conta_externa.pk,
            ),
        )

        self.assertEqual(resposta_responsavel.status_code, 200)
        self.assertEqual(resposta_conta.status_code, 302)
        self.assertEqual(Saida.objects.count(), 1)
        self.assertIsNone(Saida.objects.get().conta)


@skipUnlessDBFeature("has_select_for_update")
class ConcorrenciaPagamentoTests(TransactionTestCase):
    def setUp(self):
        self.usuario_um = get_user_model().objects.create_user(username="usuario_um")
        self.usuario_dois = get_user_model().objects.create_user(username="usuario_dois")
        self.sala = Sala.objects.create(
            nome="Nossa casa",
            orcamento_mensal=Decimal("1000.00"),
            criado_por=self.usuario_um,
        )
        MembroSala.objects.create(sala=self.sala, usuario=self.usuario_um)
        MembroSala.objects.create(sala=self.sala, usuario=self.usuario_dois)
        self.conta = Conta.objects.create(
            sala=self.sala,
            tipo=Conta.Tipo.DINHEIRO,
            nome="Conta principal",
            titular=self.usuario_um,
            saldo_inicial=Decimal("1000.00"),
            data_saldo_inicial=date(2026, 10, 1),
        )
        self.saida = Saida.objects.create(
            sala=self.sala,
            descricao="Aluguel",
            valor=Decimal("100.00"),
            responsavel=self.usuario_um,
            situacao=Saida.Situacao.PENDENTE,
            vencimento=date(2026, 10, 10),
        )

    def test_pagamentos_simultaneos_descontam_uma_unica_vez(self):
        barreira = Barrier(2)

        def pagar():
            close_old_connections()
            saida = Saida.objects.get(pk=self.saida.pk)
            conta = Conta.objects.get(pk=self.conta.pk)
            barreira.wait()
            try:
                _, foi_alterada = marcar_saida_como_paga(
                    saida,
                    date(2026, 10, 10),
                    Saida.FormaPagamento.PIX,
                    conta,
                )
                return foi_alterada
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(lambda _: pagar(), range(2)))

        self.assertEqual(resultados.count(True), 1)
        self.assertEqual(Conta.objects.get(pk=self.conta.pk).saldo_atual, Decimal("900.00"))
