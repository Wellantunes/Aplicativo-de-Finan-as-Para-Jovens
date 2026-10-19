import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from importlib import import_module
from threading import Barrier

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse

from contas.models import CartaoCredito, Conta
from salas.models import MembroSala, Sala

from .models import CompraCredito, Fatura, PagamentoFatura
from .services import (
    CartaoErro,
    atualizar_compra,
    criar_compra,
    datas_da_fatura,
    excluir_compra,
    pagar_fatura,
    prever_fatura_da_compra,
)


class FluxoCartoesTests(TestCase):
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
        self.cartao = CartaoCredito.objects.create(
            sala=self.sala,
            nome="Cartão principal",
            titular=self.criador,
            dia_fechamento=10,
            dia_vencimento=17,
        )
        self.conta = Conta.objects.create(
            sala=self.sala,
            tipo=Conta.Tipo.DINHEIRO,
            nome="Conta principal",
            titular=self.criador,
            saldo_inicial=Decimal("1000.00"),
            data_saldo_inicial=date(2026, 10, 1),
        )
        self.conta_vale = Conta.objects.create(
            sala=self.sala,
            tipo=Conta.Tipo.VALE_ALIMENTACAO,
            nome="Vale",
            titular=self.parceira,
            saldo_inicial=Decimal("500.00"),
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
        self.cartao_externo = CartaoCredito.objects.create(
            sala=self.sala_externa,
            nome="Cartão externo",
            titular=self.externo,
            dia_fechamento=5,
            dia_vencimento=12,
        )

    def dados_compra(self, **alteracoes):
        dados = {
            "cartao": self.cartao,
            "responsavel": self.criador,
            "descricao": "Mercado",
            "valor_total": Decimal("100.00"),
            "data_compra": date(2026, 10, 5),
            "quantidade_parcelas": 1,
            "custo_vida": True,
        }
        dados.update(alteracoes)
        return dados

    def dados_formulario(self, **alteracoes):
        dados = {
            "cartao": self.cartao.pk,
            "responsavel": self.criador.pk,
            "descricao": "Mercado",
            "valor_total": "100.00",
            "data_compra": "2026-10-05",
            "quantidade_parcelas": "1",
            "custo_vida": "on",
            "chave_formulario": str(uuid.uuid4()),
        }
        dados.update(alteracoes)
        return dados

    def criar_compra_teste(self, **alteracoes):
        compra, _ = criar_compra(
            self.sala,
            uuid.uuid4(),
            self.dados_compra(**alteracoes),
        )
        return compra

    def test_paginas_exigem_login(self):
        self.assertEqual(self.client.get(reverse("cartoes:lista")).status_code, 302)
        self.assertEqual(
            self.client.get(reverse("cartoes:criar_compra")).status_code,
            302,
        )

    def test_compra_ate_fechamento_entra_na_fatura_do_mes(self):
        compra = self.criar_compra_teste(data_compra=date(2026, 10, 10))

        fatura = compra.parcelas.get().fatura
        self.assertEqual((fatura.ano_referencia, fatura.mes_referencia), (2026, 10))
        self.assertEqual(fatura.data_fechamento, date(2026, 10, 10))
        self.assertEqual(fatura.data_vencimento, date(2026, 10, 17))

    def test_compra_depois_fechamento_entra_na_proxima_fatura(self):
        compra = self.criar_compra_teste(data_compra=date(2026, 10, 11))

        fatura = compra.parcelas.get().fatura
        self.assertEqual((fatura.ano_referencia, fatura.mes_referencia), (2026, 11))

    def test_parcelas_sao_distribuidas_sem_perder_centavos(self):
        compra = self.criar_compra_teste(quantidade_parcelas=3)
        valores = list(compra.parcelas.values_list("valor", flat=True))

        self.assertEqual(valores, [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")])
        self.assertEqual(sum(valores), Decimal("100.00"))
        referencias = list(
            compra.parcelas.values_list(
                "fatura__ano_referencia",
                "fatura__mes_referencia",
            )
        )
        self.assertEqual(referencias, [(2026, 10), (2026, 11), (2026, 12)])

    def test_fechamento_e_vencimento_tratam_meses_curtos(self):
        cartao = CartaoCredito.objects.create(
            sala=self.sala,
            nome="Cartão dia 31",
            titular=self.parceira,
            dia_fechamento=31,
            dia_vencimento=5,
        )
        compra = self.criar_compra_teste(
            cartao=cartao,
            data_compra=date(2026, 2, 28),
        )

        fatura = compra.parcelas.get().fatura
        self.assertEqual(fatura.data_fechamento, date(2026, 2, 28))
        self.assertEqual(fatura.data_vencimento, date(2026, 3, 5))
        self.assertEqual((fatura.ano_referencia, fatura.mes_referencia), (2026, 3))

    def test_mes_da_fatura_e_o_mes_do_vencimento(self):
        cartao = CartaoCredito.objects.create(
            sala=self.sala,
            nome="Cartão com vencimento posterior",
            titular=self.parceira,
            dia_fechamento=25,
            dia_vencimento=5,
        )

        compra_antes_fechamento = self.criar_compra_teste(
            cartao=cartao,
            descricao="Compra de outubro",
            data_compra=date(2026, 10, 20),
        )
        compra_depois_fechamento = self.criar_compra_teste(
            cartao=cartao,
            descricao="Compra de novembro",
            data_compra=date(2026, 10, 26),
        )

        fatura_novembro = compra_antes_fechamento.parcelas.get().fatura
        fatura_dezembro = compra_depois_fechamento.parcelas.get().fatura
        self.assertEqual(fatura_novembro.data_fechamento, date(2026, 10, 25))
        self.assertEqual(fatura_novembro.data_vencimento, date(2026, 11, 5))
        self.assertEqual(fatura_novembro.referencia_formatada, "11/2026")
        self.assertEqual(fatura_dezembro.data_fechamento, date(2026, 11, 25))
        self.assertEqual(fatura_dezembro.data_vencimento, date(2026, 12, 5))
        self.assertEqual(fatura_dezembro.referencia_formatada, "12/2026")

    def test_migracao_de_referencia_preserva_fatura_paga_e_saldo(self):
        cartao = CartaoCredito.objects.create(
            sala=self.sala,
            nome="Cartão com vencimento posterior",
            titular=self.parceira,
            dia_fechamento=25,
            dia_vencimento=5,
        )
        compra = self.criar_compra_teste(
            cartao=cartao,
            valor_total=Decimal("250.00"),
            data_compra=date(2026, 10, 20),
            quantidade_parcelas=2,
        )
        fatura = compra.parcelas.order_by("numero").first().fatura

        # Simula a referência antiga, que usava o mês do fechamento.
        Fatura.objects.filter(pk=fatura.pk).update(
            ano_referencia=2026,
            mes_referencia=10,
        )
        fatura.refresh_from_db()
        pagamento, _ = pagar_fatura(
            fatura,
            self.conta,
            date(2026, 11, 5),
            self.criador,
        )

        parcelas_antes = list(
            compra.parcelas.order_by("pk").values_list(
                "pk",
                "compra_id",
                "fatura_id",
                "numero",
                "valor",
            )
        )
        pagamento_antes = (
            pagamento.pk,
            pagamento.fatura_id,
            pagamento.conta_id,
            pagamento.valor,
            pagamento.data_pagamento,
        )
        saldo_antes = self.conta.saldo_atual
        datas_antes = (fatura.data_fechamento, fatura.data_vencimento)

        migracao = import_module("cartoes.migrations.0002_mes_referencia_vencimento")
        migracao.usar_mes_do_vencimento(apps, None)

        fatura.refresh_from_db()
        pagamento.refresh_from_db()
        self.assertEqual(fatura.referencia_formatada, "11/2026")
        self.assertEqual(
            (fatura.data_fechamento, fatura.data_vencimento),
            datas_antes,
        )
        self.assertEqual(
            list(
                compra.parcelas.order_by("pk").values_list(
                    "pk",
                    "compra_id",
                    "fatura_id",
                    "numero",
                    "valor",
                )
            ),
            parcelas_antes,
        )
        self.assertEqual(
            (
                pagamento.pk,
                pagamento.fatura_id,
                pagamento.conta_id,
                pagamento.valor,
                pagamento.data_pagamento,
            ),
            pagamento_antes,
        )
        self.assertEqual(self.conta.saldo_atual, saldo_antes)

    def test_compra_nao_reduz_saldo_e_pagamento_reduz_uma_vez(self):
        compra = self.criar_compra_teste(valor_total=Decimal("300.00"))
        fatura = compra.parcelas.get().fatura

        self.assertEqual(self.conta.saldo_atual, Decimal("1000.00"))
        pagamento, criado = pagar_fatura(
            fatura,
            self.conta,
            date(2026, 10, 17),
            self.parceira,
        )

        self.assertTrue(criado)
        self.assertEqual(pagamento.valor, Decimal("300.00"))
        self.assertEqual(self.conta.saldo_atual, Decimal("700.00"))

        _, criado_novamente = pagar_fatura(
            fatura,
            self.conta,
            date(2026, 10, 17),
            self.criador,
        )
        self.assertFalse(criado_novamente)
        self.assertEqual(self.conta.saldo_atual, Decimal("700.00"))

    def test_fatura_soma_parcelas_de_compras_diferentes(self):
        primeira = self.criar_compra_teste(valor_total=Decimal("100.00"))
        segunda = self.criar_compra_teste(
            descricao="Almoço",
            valor_total=Decimal("50.00"),
        )

        self.assertEqual(primeira.parcelas.get().fatura, segunda.parcelas.get().fatura)
        self.assertEqual(primeira.parcelas.get().fatura.valor_total, Decimal("150.00"))
        self.assertEqual(Fatura.objects.count(), 1)

    def test_editar_compra_recria_parcelas_e_remove_faturas_vazias(self):
        compra = self.criar_compra_teste(quantidade_parcelas=2)

        atualizar_compra(
            compra,
            self.dados_compra(
                valor_total=Decimal("90.00"),
                data_compra=date(2026, 11, 11),
                quantidade_parcelas=3,
            ),
        )
        compra.refresh_from_db()

        self.assertEqual(compra.parcelas.count(), 3)
        self.assertEqual(sum(p.valor for p in compra.parcelas.all()), Decimal("90.00"))
        self.assertEqual(
            list(compra.parcelas.values_list("fatura__mes_referencia", flat=True)),
            [12, 1, 2],
        )
        self.assertFalse(Fatura.objects.filter(mes_referencia=10).exists())

    def test_excluir_compra_remove_parcelas_de_faturas_nao_pagas(self):
        compra = self.criar_compra_teste(quantidade_parcelas=2)

        excluir_compra(compra)

        self.assertFalse(CompraCredito.objects.exists())
        self.assertFalse(Fatura.objects.exists())

    def test_compra_de_fatura_paga_nao_pode_ser_editada_nem_excluida(self):
        compra = self.criar_compra_teste()
        pagar_fatura(
            compra.parcelas.get().fatura,
            self.conta,
            date(2026, 10, 17),
            self.criador,
        )

        with self.assertRaisesMessage(CartaoErro, "fatura paga"):
            atualizar_compra(compra, self.dados_compra(valor_total=Decimal("80.00")))
        with self.assertRaisesMessage(CartaoErro, "fatura paga"):
            excluir_compra(compra)

    def test_reenvio_do_formulario_nao_duplica_compra(self):
        self.client.force_login(self.criador)
        dados = self.dados_formulario()

        primeira = self.client.post(reverse("cartoes:criar_compra"), dados)
        segunda = self.client.post(reverse("cartoes:criar_compra"), dados)

        self.assertEqual(primeira.status_code, 302)
        self.assertEqual(segunda.status_code, 302)
        self.assertEqual(CompraCredito.objects.count(), 1)
        self.assertEqual(Fatura.objects.count(), 1)

    def test_reenvio_do_pagamento_nao_duplica_despesa(self):
        compra = self.criar_compra_teste(valor_total=Decimal("200.00"))
        fatura = compra.parcelas.get().fatura
        self.client.force_login(self.parceira)
        dados = {"data_pagamento": "2026-10-17", "conta": self.conta.pk}

        primeira = self.client.post(
            reverse("cartoes:pagar_fatura", args=[fatura.pk]),
            dados,
        )
        segunda = self.client.post(
            reverse("cartoes:pagar_fatura", args=[fatura.pk]),
            dados,
        )

        self.assertEqual(primeira.status_code, 302)
        self.assertEqual(segunda.status_code, 302)
        self.assertEqual(PagamentoFatura.objects.count(), 1)
        self.assertEqual(self.conta.saldo_atual, Decimal("800.00"))

    def test_pagamento_exige_conta_em_dinheiro_da_sala(self):
        fatura = self.criar_compra_teste().parcelas.get().fatura
        self.client.force_login(self.criador)

        response = self.client.post(
            reverse("cartoes:pagar_fatura", args=[fatura.pk]),
            {"data_pagamento": "2026-10-17", "conta": self.conta_vale.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PagamentoFatura.objects.exists())

    def test_saldo_insuficiente_avisa_mas_permite_pagamento(self):
        fatura = self.criar_compra_teste(valor_total=Decimal("1200.00")).parcelas.get().fatura
        self.client.force_login(self.criador)

        response = self.client.post(
            reverse("cartoes:pagar_fatura", args=[fatura.pk]),
            {"data_pagamento": "2026-10-17", "conta": self.conta.pk},
            follow=True,
        )

        self.assertContains(response, "ficou negativo")
        self.assertEqual(self.conta.saldo_atual, Decimal("-200.00"))

    def test_os_dois_membros_podem_administrar_compras(self):
        self.client.force_login(self.parceira)

        response = self.client.post(
            reverse("cartoes:criar_compra"),
            self.dados_formulario(responsavel=self.parceira.pk),
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(CompraCredito.objects.filter(responsavel=self.parceira).exists())

    def test_usuario_externo_nao_consulta_nem_altera_compra_ou_fatura(self):
        compra = self.criar_compra_teste()
        fatura = compra.parcelas.get().fatura
        self.client.force_login(self.externo)

        lista = self.client.get(reverse("cartoes:lista"))
        editar = self.client.get(reverse("cartoes:editar_compra", args=[compra.pk]))
        excluir = self.client.post(reverse("cartoes:excluir_compra", args=[compra.pk]))
        detalhe = self.client.get(reverse("cartoes:detalhe_fatura", args=[fatura.pk]))
        pagar = self.client.get(reverse("cartoes:pagar_fatura", args=[fatura.pk]))

        self.assertNotContains(lista, compra.descricao)
        self.assertEqual(editar.status_code, 404)
        self.assertEqual(excluir.status_code, 404)
        self.assertEqual(detalhe.status_code, 404)
        self.assertEqual(pagar.status_code, 404)

    def test_cartao_e_responsavel_de_outra_sala_sao_recusados(self):
        self.client.force_login(self.criador)

        resposta_cartao = self.client.post(
            reverse("cartoes:criar_compra"),
            self.dados_formulario(cartao=self.cartao_externo.pk),
        )
        resposta_responsavel = self.client.post(
            reverse("cartoes:criar_compra"),
            self.dados_formulario(responsavel=self.externo.pk),
        )

        self.assertEqual(resposta_cartao.status_code, 200)
        self.assertEqual(resposta_responsavel.status_code, 200)
        self.assertFalse(CompraCredito.objects.exists())

    def test_parcela_de_custo_de_vida_aparece_no_mes_da_fatura(self):
        self.criar_compra_teste(
            valor_total=Decimal("90.00"),
            data_compra=date(2026, 10, 11),
            quantidade_parcelas=2,
            custo_vida=True,
        )
        self.client.force_login(self.criador)

        outubro = self.client.get(reverse("saidas:lista"), {"mes": "2026-10"})
        novembro = self.client.get(reverse("saidas:lista"), {"mes": "2026-11"})

        self.assertEqual(outubro.context["total_custo_cartao"], Decimal("0.00"))
        self.assertEqual(novembro.context["total_custo_cartao"], Decimal("45.00"))


class NovasRegrasDeCartaoTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(username="usuario")
        self.externo = get_user_model().objects.create_user(username="externo")
        self.cartao = CartaoCredito.objects.create(
            proprietario_usuario=self.usuario,
            titular=self.usuario,
            nome="Nubank",
            cor_simbolo=CartaoCredito.CorSimbolo.ROXO,
            regra_fechamento=CartaoCredito.RegraData.ULTIMO_DIA,
            dia_fechamento=None,
            regra_vencimento=CartaoCredito.RegraData.DIA_FIXO,
            dia_vencimento=8,
        )

    def criar_compra(self, data_compra, cartao=None, fatura_destino=None):
        cartao = cartao or self.cartao
        return criar_compra(
            sala=None,
            proprietario_usuario=self.usuario,
            autor=self.usuario,
            chave_idempotencia=uuid.uuid4(),
            dados={
                "cartao": cartao,
                "responsavel": self.usuario,
                "descricao": "Compra teste",
                "valor_total": Decimal("80.00"),
                "data_compra": data_compra,
                "quantidade_parcelas": 1,
                "custo_vida": False,
            },
            fatura_destino=fatura_destino,
        )[0]

    def test_exemplo_a_ultimo_dia_com_vencimento_dia_oito(self):
        for dia in (16, 30, 31):
            fechamento, vencimento, _ = prever_fatura_da_compra(
                self.cartao, date(2026, 10, dia)
            )
            self.assertEqual(fechamento, date(2026, 10, 31))
            self.assertEqual(vencimento, date(2026, 11, 8))

        fechamento, vencimento, _ = prever_fatura_da_compra(
            self.cartao, date(2026, 11, 1)
        )
        self.assertEqual(fechamento, date(2026, 11, 30))
        self.assertEqual(vencimento, date(2026, 12, 8))

    def test_exemplo_b_dia_trinta_nao_equivale_ao_ultimo_dia(self):
        self.cartao.regra_fechamento = CartaoCredito.RegraData.DIA_FIXO
        self.cartao.dia_fechamento = 30
        self.cartao.save()

        fechamento, vencimento, _ = prever_fatura_da_compra(
            self.cartao, date(2026, 10, 30)
        )
        self.assertEqual((fechamento, vencimento), (date(2026, 10, 30), date(2026, 11, 8)))

        fechamento, vencimento, _ = prever_fatura_da_compra(
            self.cartao, date(2026, 10, 31)
        )
        self.assertEqual((fechamento, vencimento), (date(2026, 11, 30), date(2026, 12, 8)))

    def test_exemplo_c_vencimento_no_ultimo_dia(self):
        self.cartao.regra_fechamento = CartaoCredito.RegraData.DIA_FIXO
        self.cartao.dia_fechamento = 20
        self.cartao.regra_vencimento = CartaoCredito.RegraData.ULTIMO_DIA
        self.cartao.dia_vencimento = None
        self.cartao.save()

        self.assertEqual(
            datas_da_fatura(self.cartao, 2026, 10),
            (date(2026, 10, 20), date(2026, 10, 31)),
        )
        fechamento, vencimento, _ = prever_fatura_da_compra(
            self.cartao, date(2026, 10, 21)
        )
        self.assertEqual((fechamento, vencimento), (date(2026, 11, 20), date(2026, 11, 30)))

    def test_fevereiro_e_virada_de_ano(self):
        self.assertEqual(
            self.cartao.data_fechamento_no_mes(2027, 2), date(2027, 2, 28)
        )
        self.assertEqual(
            self.cartao.data_fechamento_no_mes(2028, 2), date(2028, 2, 29)
        )
        fechamento, vencimento, _ = prever_fatura_da_compra(
            self.cartao, date(2026, 12, 31)
        )
        self.assertEqual((fechamento, vencimento), (date(2026, 12, 31), date(2027, 1, 8)))

    def test_editar_regra_preserva_ciclo_existente(self):
        self.cartao.regra_fechamento = CartaoCredito.RegraData.DIA_FIXO
        self.cartao.dia_fechamento = 25
        self.cartao.save()
        primeira = self.criar_compra(date(2026, 10, 20))
        fatura_original = primeira.parcelas.get().fatura

        self.cartao.dia_fechamento = 20
        self.cartao.dia_vencimento = 12
        self.cartao.save()
        segunda = self.criar_compra(date(2026, 10, 21))

        self.assertEqual(segunda.parcelas.get().fatura, fatura_original)
        self.assertEqual(fatura_original.data_fechamento, date(2026, 10, 25))
        self.assertEqual(fatura_original.data_vencimento, date(2026, 11, 8))

    def test_escolha_manual_aceita_somente_fatura_aberta_do_cartao(self):
        fatura_manual = self.criar_compra(date(2026, 11, 1)).parcelas.get().fatura
        compra = self.criar_compra(
            date(2026, 10, 1), fatura_destino=fatura_manual
        )
        self.assertEqual(compra.parcelas.get().fatura, fatura_manual)

        outro_cartao = CartaoCredito.objects.create(
            proprietario_usuario=self.usuario,
            titular=self.usuario,
            nome="Outro",
            dia_fechamento=10,
            dia_vencimento=20,
        )
        with self.assertRaisesMessage(CartaoErro, "mesmo cartão"):
            self.criar_compra(
                date(2026, 10, 1),
                cartao=outro_cartao,
                fatura_destino=fatura_manual,
            )

    def test_pagamento_sem_conta_nao_altera_saldo_de_conta_existente(self):
        conta = Conta.objects.create(
            proprietario_usuario=self.usuario,
            titular=self.usuario,
            tipo=Conta.Tipo.DINHEIRO,
            nome="Conta",
            saldo_inicial=Decimal("500.00"),
            data_saldo_inicial=date(2026, 10, 1),
        )
        fatura = self.criar_compra(date(2026, 10, 1)).parcelas.get().fatura

        pagamento, criado = pagar_fatura(
            fatura, None, date(2026, 11, 8), self.usuario
        )

        self.assertTrue(criado)
        self.assertIsNone(pagamento.conta)
        self.assertEqual(conta.saldo_atual, Decimal("500.00"))

    def test_cartao_aparece_apenas_em_lancamentos_de_saida_e_arquivado_some(self):
        self.client.force_login(self.usuario)
        saidas = self.client.get(reverse("core:lancamentos"), {"tipo": "saida"})
        entradas = self.client.get(reverse("core:lancamentos"), {"tipo": "entrada"})
        self.assertContains(saidas, "Cartão Nubank")
        self.assertContains(saidas, reverse("cartoes:criar_compra_cartao", args=[self.cartao.pk]))
        self.assertNotContains(entradas, "Cartão Nubank")

        self.cartao.arquivado = True
        self.cartao.save(update_fields=["arquivado"])
        saidas = self.client.get(reverse("core:lancamentos"), {"tipo": "saida"})
        compra = self.client.get(
            reverse("cartoes:criar_compra_cartao", args=[self.cartao.pk])
        )
        self.assertNotContains(saidas, "Cartão Nubank")
        self.assertEqual(compra.status_code, 404)

    def test_compra_rapida_recalcula_no_backend_e_nao_duplica(self):
        self.client.force_login(self.usuario)
        chave = str(uuid.uuid4())
        dados = {
            "descricao": "Pizza",
            "valor_total": "80.00",
            "data_compra": "2026-10-31",
            "chave_formulario": chave,
        }
        url = reverse("cartoes:criar_compra_cartao", args=[self.cartao.pk])
        primeira = self.client.post(url, dados)
        segunda = self.client.post(url, dados)

        self.assertEqual(primeira.status_code, 302)
        self.assertEqual(segunda.status_code, 302)
        self.assertEqual(CompraCredito.objects.count(), 1)
        fatura = CompraCredito.objects.get().parcelas.get().fatura
        self.assertEqual(fatura.data_fechamento, date(2026, 10, 31))
        self.assertEqual(fatura.data_vencimento, date(2026, 11, 8))

    def test_ajuste_de_fatura_exige_confirmacao_e_preserva_compra(self):
        compra = self.criar_compra(date(2026, 10, 20))
        fatura = compra.parcelas.get().fatura
        self.client.force_login(self.usuario)
        url = reverse("cartoes:ajustar_fatura", args=[fatura.pk])

        resposta = self.client.post(
            url,
            {
                "data_fechamento": "2026-10-19",
                "data_vencimento": "2026-12-08",
            },
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Confirme que os indicadores")
        self.assertContains(resposta, "Compra teste")

        resposta = self.client.post(
            url,
            {
                "data_fechamento": "2026-10-19",
                "data_vencimento": "2026-12-08",
                "confirmar_mudanca_mes": "on",
                "confirmar_compras_fora_ciclo": "on",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        fatura.refresh_from_db()
        compra.refresh_from_db()
        self.assertEqual(fatura.data_fechamento, date(2026, 10, 19))
        self.assertEqual(fatura.data_vencimento, date(2026, 12, 8))
        self.assertEqual(fatura.referencia_formatada, "12/2026")
        self.assertEqual(compra.parcelas.get().fatura, fatura)

    def test_ajuste_nao_pode_ultrapassar_fechamento_seguinte(self):
        primeira = self.criar_compra(date(2026, 10, 1)).parcelas.get().fatura
        self.criar_compra(date(2026, 11, 1))
        self.client.force_login(self.usuario)

        resposta = self.client.post(
            reverse("cartoes:ajustar_fatura", args=[primeira.pk]),
            {
                "data_fechamento": "2026-12-01",
                "data_vencimento": "2027-01-08",
                "confirmar_mudanca_mes": "on",
                "confirmar_compras_fora_ciclo": "on",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "antes da próxima fatura")

    def test_fatura_paga_nao_pode_ser_ajustada(self):
        fatura = self.criar_compra(date(2026, 10, 1)).parcelas.get().fatura
        pagar_fatura(fatura, None, date(2026, 11, 8), self.usuario)
        self.client.force_login(self.usuario)

        resposta = self.client.get(
            reverse("cartoes:ajustar_fatura", args=[fatura.pk]), follow=True
        )

        self.assertContains(resposta, "fatura paga não pode")

    def test_pagina_inicial_mostra_cartoes_sem_formulario_ou_filtros(self):
        self.client.force_login(self.usuario)

        resposta = self.client.get(reverse("cartoes:lista"))

        self.assertContains(resposta, "Nubank")
        self.assertContains(resposta, "Cadastrar cartão")
        self.assertNotContains(resposta, "Aplicar filtros")
        self.assertNotContains(resposta, "Registrar compra no crédito")

    def test_usuario_externo_nao_acessa_cartao_compra_ou_previa(self):
        self.client.force_login(self.externo)
        self.assertEqual(
            self.client.get(
                reverse("cartoes:detalhe_cartao", args=[self.cartao.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("cartoes:criar_compra_cartao", args=[self.cartao.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("cartoes:previa_fatura", args=[self.cartao.pk]),
                {"data": "2026-10-10"},
            ).status_code,
            404,
        )


@skipUnlessDBFeature("has_select_for_update")
class ConcorrenciaPagamentoFaturaTests(TransactionTestCase):
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
        self.cartao = CartaoCredito.objects.create(
            sala=self.sala,
            nome="Cartão",
            titular=self.usuario_um,
            dia_fechamento=10,
            dia_vencimento=17,
        )
        self.conta = Conta.objects.create(
            sala=self.sala,
            tipo=Conta.Tipo.DINHEIRO,
            nome="Conta",
            titular=self.usuario_um,
            saldo_inicial=Decimal("1000.00"),
            data_saldo_inicial=date(2026, 10, 1),
        )
        compra, _ = criar_compra(
            self.sala,
            uuid.uuid4(),
            {
                "cartao": self.cartao,
                "responsavel": self.usuario_um,
                "descricao": "Compra",
                "valor_total": Decimal("100.00"),
                "data_compra": date(2026, 10, 1),
                "quantidade_parcelas": 1,
                "custo_vida": False,
            },
        )
        self.fatura = compra.parcelas.get().fatura

    def test_pagamentos_simultaneos_descontam_uma_unica_vez(self):
        barreira = Barrier(2)

        def pagar(usuario_id):
            close_old_connections()
            fatura = Fatura.objects.get(pk=self.fatura.pk)
            conta = Conta.objects.get(pk=self.conta.pk)
            usuario = get_user_model().objects.get(pk=usuario_id)
            barreira.wait()
            try:
                _, criado = pagar_fatura(
                    fatura,
                    conta,
                    date(2026, 10, 17),
                    usuario,
                )
                return criado
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(
                executor.map(pagar, [self.usuario_um.pk, self.usuario_dois.pk])
            )

        self.assertEqual(resultados.count(True), 1)
        self.assertEqual(PagamentoFatura.objects.count(), 1)
        self.assertEqual(Conta.objects.get(pk=self.conta.pk).saldo_atual, Decimal("900.00"))
