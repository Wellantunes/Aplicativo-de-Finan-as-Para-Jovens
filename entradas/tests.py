import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contas.models import Conta
from salas.models import MembroSala, Sala

from .models import (
    ConfiguracaoDizimo,
    DevolucaoDizimo,
    Entrada,
    FormaCalculoDizimo,
    TipoEntrada,
    calcular_dizimo,
)
from .services import EntradaErro, criar_entrada, registrar_devolucao


class CalculoDizimoTests(TestCase):
    def test_percentual_e_arredondado_para_centavos(self):
        resultado = calcular_dizimo(
            valor=Decimal("100.05"),
            calcular=True,
            forma=FormaCalculoDizimo.PERCENTUAL,
            percentual=Decimal("10"),
        )

        self.assertEqual(resultado, Decimal("10.01"))

    def test_valor_manual_e_mantido_em_centavos(self):
        resultado = calcular_dizimo(
            valor=Decimal("1000"),
            calcular=True,
            forma=FormaCalculoDizimo.VALOR_MANUAL,
            valor_manual=Decimal("123.456"),
        )

        self.assertEqual(resultado, Decimal("123.46"))

    def test_sem_calculo_retorna_zero(self):
        resultado = calcular_dizimo(
            valor=Decimal("1000"),
            calcular=False,
            forma="",
        )

        self.assertEqual(resultado, Decimal("0.00"))


class FluxoEntradasTests(TestCase):
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
            saldo_inicial=Decimal("100.00"),
            data_saldo_inicial=date(2026, 10, 1),
        )
        self.outra_conta_dinheiro = Conta.objects.create(
            sala=self.sala,
            tipo=Conta.Tipo.DINHEIRO,
            nome="Carteira",
            titular=self.parceira,
            saldo_inicial=Decimal("50.00"),
            data_saldo_inicial=date(2026, 10, 1),
        )
        self.conta_vale = Conta.objects.create(
            sala=self.sala,
            tipo=Conta.Tipo.VALE_ALIMENTACAO,
            nome="Vale mercado",
            titular=self.parceira,
            saldo_inicial=Decimal("0.00"),
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
            saldo_inicial=Decimal("10.00"),
            data_saldo_inicial=date(2026, 10, 1),
        )

    def dados_entrada(self, **alteracoes):
        dados = {
            "pessoa": self.criador.pk,
            "tipo": TipoEntrada.SALARIO,
            "descricao": "Salário de outubro",
            "valor": "3000.00",
            "data": "2026-10-05",
            "conta_destino": self.conta_dinheiro.pk,
            "calcular_dizimo": "on",
            "forma_calculo": FormaCalculoDizimo.PERCENTUAL,
            "percentual_dizimo": "10.00",
            "valor_dizimo_manual": "",
            "chave_formulario": str(uuid.uuid4()),
        }
        dados.update(alteracoes)
        return dados

    def criar_entrada_salario(self, valor="3000.00"):
        entrada, _ = criar_entrada(
            sala=self.sala,
            chave_idempotencia=uuid.uuid4(),
            dados={
                "pessoa": self.criador,
                "tipo": TipoEntrada.SALARIO,
                "descricao": "Salário de outubro",
                "valor": Decimal(valor),
                "data": date(2026, 10, 5),
                "conta_destino": self.conta_dinheiro,
                "calcular_dizimo": True,
                "forma_calculo": FormaCalculoDizimo.PERCENTUAL,
                "percentual_dizimo": Decimal("10.00"),
                "valor_dizimo_manual": None,
            },
        )
        return entrada

    def registrar_devolucao_parcial(self, entrada, valor="200.00"):
        devolucao, _ = registrar_devolucao(
            entrada=entrada,
            usuario=self.parceira,
            chave_idempotencia=uuid.uuid4(),
            dados={
                "valor": Decimal(valor),
                "data": date(2026, 10, 10),
                "conta": self.conta_dinheiro,
            },
        )
        return devolucao

    def test_paginas_exigem_login(self):
        self.assertEqual(self.client.get(reverse("entradas:lista")).status_code, 302)
        self.assertEqual(self.client.get(reverse("entradas:criar")).status_code, 302)

    def test_exemplo_completo_produz_os_saldos_informados(self):
        salario = self.criar_entrada_salario()
        criar_entrada(
            sala=self.sala,
            chave_idempotencia=uuid.uuid4(),
            dados={
                "pessoa": self.parceira,
                "tipo": TipoEntrada.VALE_ALIMENTACAO,
                "descricao": "Vale de outubro",
                "valor": Decimal("630.00"),
                "data": date(2026, 10, 5),
                "conta_destino": self.conta_vale,
                "calcular_dizimo": False,
                "forma_calculo": "",
                "percentual_dizimo": None,
                "valor_dizimo_manual": None,
            },
        )

        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("3100.00"))
        self.assertEqual(self.conta_vale.saldo_atual, Decimal("630.00"))
        self.assertEqual(salario.dizimo_previsto, Decimal("300.00"))

        self.registrar_devolucao_parcial(salario, "200.00")
        salario.refresh_from_db()

        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("2900.00"))
        self.assertEqual(self.conta_vale.saldo_atual, Decimal("630.00"))
        self.assertEqual(salario.valor_devolvido, Decimal("200.00"))
        self.assertEqual(salario.dizimo_restante, Decimal("100.00"))

    def test_dizimo_previsto_nao_reduz_saldo(self):
        entrada = self.criar_entrada_salario()

        self.assertEqual(entrada.dizimo_previsto, Decimal("300.00"))
        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("3100.00"))

    def test_vale_com_dizimo_exige_devolucao_em_dinheiro(self):
        entrada, _ = criar_entrada(
            sala=self.sala,
            chave_idempotencia=uuid.uuid4(),
            dados={
                "pessoa": self.parceira,
                "tipo": TipoEntrada.VALE_ALIMENTACAO,
                "descricao": "Vale com dízimo",
                "valor": Decimal("500.00"),
                "data": date(2026, 10, 5),
                "conta_destino": self.conta_vale,
                "calcular_dizimo": True,
                "forma_calculo": FormaCalculoDizimo.PERCENTUAL,
                "percentual_dizimo": Decimal("10"),
                "valor_dizimo_manual": None,
            },
        )

        self.registrar_devolucao_parcial(entrada, "50.00")

        self.assertEqual(self.conta_vale.saldo_atual, Decimal("500.00"))
        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("50.00"))

    def test_entrada_avulsa_nao_exige_conta(self):
        self.client.force_login(self.criador)

        response = self.client.post(
            reverse("entradas:criar"),
            self.dados_entrada(
                tipo=TipoEntrada.VALE_ALIMENTACAO,
                conta_destino=self.conta_dinheiro.pk,
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(Entrada.objects.get().conta_destino)

    def test_valor_da_entrada_deve_ser_maior_que_zero(self):
        self.client.force_login(self.criador)

        response = self.client.post(
            reverse("entradas:criar"),
            self.dados_entrada(valor="0"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Entrada.objects.exists())

    def test_reenvio_do_formulario_nao_duplica_entrada(self):
        self.client.force_login(self.criador)
        dados = self.dados_entrada()

        primeira_resposta = self.client.post(reverse("entradas:criar"), dados)
        segunda_resposta = self.client.post(reverse("entradas:criar"), dados)

        self.assertEqual(primeira_resposta.status_code, 302)
        self.assertEqual(segunda_resposta.status_code, 302)
        self.assertEqual(Entrada.objects.count(), 1)
        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("100.00"))

    def test_reenvio_da_devolucao_nao_duplica_pagamento(self):
        entrada = self.criar_entrada_salario()
        self.client.force_login(self.parceira)
        chave = str(uuid.uuid4())
        dados = {
            "valor": "200.00",
            "data": "2026-10-10",
            "conta": self.conta_dinheiro.pk,
            "chave_formulario": chave,
        }

        primeira_resposta = self.client.post(
            reverse("entradas:devolver", args=[entrada.pk]),
            dados,
        )
        segunda_resposta = self.client.post(
            reverse("entradas:devolver", args=[entrada.pk]),
            dados,
        )

        self.assertEqual(primeira_resposta.status_code, 302)
        self.assertEqual(segunda_resposta.status_code, 302)
        self.assertEqual(DevolucaoDizimo.objects.count(), 1)
        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("2900.00"))

    def test_devolucao_nao_pode_superar_valor_restante(self):
        entrada = self.criar_entrada_salario()

        with self.assertRaisesMessage(EntradaErro, "supera o dízimo restante"):
            self.registrar_devolucao_parcial(entrada, "300.01")

        self.assertFalse(DevolucaoDizimo.objects.exists())

    def test_editar_entrada_preserva_vinculo_historico_com_conta(self):
        entrada = self.criar_entrada_salario("3000.00")
        self.client.force_login(self.parceira)

        response = self.client.post(
            reverse("entradas:editar", args=[entrada.pk]),
            self.dados_entrada(
                valor="2500.00",
                conta_destino=self.outra_conta_dinheiro.pk,
            ),
        )

        self.assertEqual(response.status_code, 302)
        entrada.refresh_from_db()
        self.assertEqual(entrada.valor, Decimal("2500.00"))
        self.assertEqual(entrada.conta_destino, self.conta_dinheiro)
        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("2600.00"))
        self.assertEqual(self.outra_conta_dinheiro.saldo_atual, Decimal("50.00"))

    def test_conta_com_movimento_nao_pode_mudar_de_tipo(self):
        self.criar_entrada_salario()
        self.client.force_login(self.criador)

        response = self.client.post(
            reverse("contas:editar_conta", args=[self.conta_dinheiro.pk]),
            {
                "tipo": Conta.Tipo.VALE_ALIMENTACAO,
                "nome": self.conta_dinheiro.nome,
                "titular": self.criador.pk,
                "saldo_inicial": "100.00",
                "data_saldo_inicial": "2026-10-01",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "já possui movimentos")
        self.conta_dinheiro.refresh_from_db()
        self.assertEqual(self.conta_dinheiro.tipo, Conta.Tipo.DINHEIRO)

    def test_excluir_entrada_corrige_saldo(self):
        entrada = self.criar_entrada_salario()
        self.client.force_login(self.criador)

        response = self.client.post(reverse("entradas:excluir", args=[entrada.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Entrada.objects.exists())
        self.assertEqual(self.conta_dinheiro.saldo_atual, Decimal("100.00"))

    def test_entrada_com_devolucao_nao_pode_ser_editada_nem_excluida(self):
        entrada = self.criar_entrada_salario()
        self.registrar_devolucao_parcial(entrada)
        self.client.force_login(self.parceira)

        resposta_edicao = self.client.get(
            reverse("entradas:editar", args=[entrada.pk]),
            follow=True,
        )
        resposta_exclusao = self.client.post(
            reverse("entradas:excluir", args=[entrada.pk]),
            follow=True,
        )

        self.assertContains(resposta_edicao, "não pode ser editada")
        self.assertContains(resposta_exclusao, "não pode ser excluída")
        self.assertTrue(Entrada.objects.filter(pk=entrada.pk).exists())

    def test_alterar_configuracao_nao_recalcula_entrada_antiga(self):
        configuracao = ConfiguracaoDizimo.objects.create(
            sala=self.sala,
            pessoa=self.criador,
            tipo_entrada=TipoEntrada.SALARIO,
            calcular_dizimo=True,
            forma_calculo=FormaCalculoDizimo.PERCENTUAL,
            percentual_dizimo=Decimal("10"),
        )
        entrada = self.criar_entrada_salario()

        configuracao.percentual_dizimo = Decimal("20")
        configuracao.save(update_fields=["percentual_dizimo"])
        entrada.refresh_from_db()

        self.assertEqual(entrada.dizimo_previsto, Decimal("300.00"))

    def test_os_dois_membros_podem_administrar_entradas(self):
        self.client.force_login(self.parceira)

        response = self.client.post(
            reverse("entradas:criar"),
            self.dados_entrada(pessoa=self.parceira.pk),
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Entrada.objects.filter(pessoa=self.parceira).exists())

    def test_usuario_externo_nao_consulta_nem_altera_entrada(self):
        entrada = self.criar_entrada_salario()
        self.client.force_login(self.externo)

        resposta_lista = self.client.get(reverse("entradas:lista"))
        resposta_editar = self.client.get(
            reverse("entradas:editar", args=[entrada.pk])
        )
        resposta_excluir = self.client.post(
            reverse("entradas:excluir", args=[entrada.pk])
        )
        resposta_devolver = self.client.get(
            reverse("entradas:devolver", args=[entrada.pk])
        )

        self.assertNotContains(resposta_lista, entrada.descricao)
        self.assertEqual(resposta_editar.status_code, 404)
        self.assertEqual(resposta_excluir.status_code, 404)
        self.assertEqual(resposta_devolver.status_code, 404)

    def test_lista_usa_data_prevista_e_nao_exibe_filtros(self):
        entrada = Entrada.objects.create(
            sala=self.sala,
            autor=self.criador,
            pessoa=self.criador,
            tipo=TipoEntrada.EXTRA,
            descricao="Entrada de novembro recebida em dezembro",
            valor=Decimal("500.00"),
            situacao=Entrada.Situacao.RECEBIDA,
            data_prevista=date(2026, 11, 20),
            data=date(2026, 12, 2),
        )
        self.client.force_login(self.criador)

        novembro = self.client.get(
            reverse("entradas:lista"), {"mes": "2026-11"}
        )
        dezembro = self.client.get(
            reverse("entradas:lista"), {"mes": "2026-12"}
        )

        self.assertContains(novembro, entrada.descricao)
        self.assertNotContains(dezembro, entrada.descricao)
        self.assertNotContains(novembro, "Aplicar filtros")
        self.assertContains(novembro, self.sala.nome)
        self.assertContains(
            novembro,
            f'{reverse("core:lancamentos")}?tipo=entrada&amp;mes=2026-11',
        )
        self.assertNotContains(novembro, reverse("entradas:criar"))

    def test_lista_usa_talheres_para_vale_sem_depender_da_descricao(self):
        self.criar_entrada_salario("2700.00")
        entrada = Entrada.objects.create(
            sala=self.sala,
            autor=self.criador,
            pessoa=self.criador,
            tipo=TipoEntrada.VALE_ALIMENTACAO,
            descricao="Benefício com nome livre",
            valor=Decimal("280.00"),
            situacao=Entrada.Situacao.RECEBIDA,
            data_prevista=date(2026, 10, 16),
            data=date(2026, 10, 16),
            conta_destino=self.conta_vale,
        )
        self.client.force_login(self.criador)

        response = self.client.get(reverse("entradas:lista"), {"mes": "2026-10"})

        self.assertContains(response, entrada.descricao)
        self.assertEqual(response.context["total_entradas_dinheiro"], Decimal("2700.00"))
        self.assertEqual(response.context["total_entradas_vale"], Decimal("280.00"))
        self.assertContains(response, "Vale-alimentação/refeição")
        self.assertContains(response, "R$ 2.700,00")
        self.assertContains(response, "R$ 280,00")
        self.assertContains(response, "dropduo/icons/talheres.png")
        self.assertEqual(entrada.caminho_simbolo, "dropduo/icons/talheres.png")

    def test_pessoa_externa_e_recusada_e_conta_postada_e_ignorada(self):
        self.client.force_login(self.criador)

        resposta_pessoa = self.client.post(
            reverse("entradas:criar"),
            self.dados_entrada(pessoa=self.externo.pk),
        )
        resposta_conta = self.client.post(
            reverse("entradas:criar"),
            self.dados_entrada(conta_destino=self.conta_externa.pk),
        )

        self.assertEqual(resposta_pessoa.status_code, 200)
        self.assertEqual(resposta_conta.status_code, 302)
        self.assertEqual(Entrada.objects.count(), 1)
        self.assertIsNone(Entrada.objects.get().conta_destino)

    def test_configuracao_e_individual_por_pessoa_e_tipo(self):
        ConfiguracaoDizimo.objects.create(
            sala=self.sala,
            pessoa=self.criador,
            tipo_entrada=TipoEntrada.SALARIO,
            calcular_dizimo=True,
            forma_calculo=FormaCalculoDizimo.PERCENTUAL,
            percentual_dizimo=Decimal("10"),
        )
        ConfiguracaoDizimo.objects.create(
            sala=self.sala,
            pessoa=self.parceira,
            tipo_entrada=TipoEntrada.SALARIO,
            calcular_dizimo=True,
            forma_calculo=FormaCalculoDizimo.PERCENTUAL,
            percentual_dizimo=Decimal("5"),
        )

        self.assertEqual(self.sala.configuracoes_dizimo.count(), 2)
