from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cartoes.forms import CompraCreditoForm
from contas.forms import ContaForm
from core.campos import ValorBrasileiroField
from contas.models import Conta
from entradas.forms import EntradaForm
from entradas.models import Entrada, TipoEntrada
from saidas.forms import SaidaForm
from saidas.models import Saida
from salas.models import MembroSala, Sala


class ListagensMobileTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(username="lista_mobile")
        self.sala = Sala.objects.create(
            nome="Casa",
            orcamento_mensal=Decimal("2000.00"),
            criado_por=self.usuario,
        )
        MembroSala.objects.create(sala=self.sala, usuario=self.usuario)
        sessao = self.client.session
        sessao["espaco_financeiro"] = "sala"
        sessao.save()
        self.conta = Conta.objects.create(
            sala=self.sala,
            tipo=Conta.Tipo.DINHEIRO,
            nome="Conta",
            titular=self.usuario,
            saldo_inicial=Decimal("0.00"),
            data_saldo_inicial=date(2026, 1, 1),
        )
        self.client.force_login(self.usuario)

    def test_entradas_sao_paginadas_em_dez_registros(self):
        for numero in range(12):
            Entrada.objects.create(
                sala=self.sala,
                pessoa=self.usuario,
                tipo=TipoEntrada.EXTRA,
                descricao=f"Entrada {numero}",
                valor=Decimal("10.00"),
                data=date(2026, 10, 1),
                conta_destino=self.conta,
            )

        response = self.client.get(reverse("entradas:lista"), {"page": 2})

        pagina = response.context["entradas"]
        self.assertEqual(pagina.paginator.count, 12)
        self.assertEqual(len(pagina), 2)
        self.assertContains(response, "Página 2 de 2")

    def test_filtro_de_entrada_por_mes(self):
        for mes in (9, 10):
            Entrada.objects.create(
                sala=self.sala,
                pessoa=self.usuario,
                tipo=TipoEntrada.EXTRA,
                descricao=f"Entrada do mês {mes}",
                valor=Decimal("10.00"),
                data=date(2026, mes, 1),
                conta_destino=self.conta,
            )

        response = self.client.get(reverse("entradas:lista"), {"mes": "2026-10"})

        self.assertContains(response, "Entrada do mês 10")
        self.assertNotContains(response, "Entrada do mês 9")

    def test_saidas_sao_paginadas_em_dez_registros(self):
        for numero in range(11):
            Saida.objects.create(
                sala=self.sala,
                descricao=f"Conta {numero}",
                valor=Decimal("10.00"),
                responsavel=self.usuario,
                situacao=Saida.Situacao.PENDENTE,
                vencimento=date(2026, 10, 20),
            )

        response = self.client.get(reverse("saidas:lista"), {"page": 2})

        pagina = response.context["saidas"]
        self.assertEqual(pagina.paginator.count, 11)
        self.assertEqual(len(pagina), 1)


class TecladoDosFormulariosTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(username="formularios")
        self.sala = Sala.objects.create(
            nome="Casa",
            orcamento_mensal=Decimal("2000.00"),
            criado_por=self.usuario,
        )
        MembroSala.objects.create(sala=self.sala, usuario=self.usuario)

    def test_valores_abrem_teclado_decimal(self):
        formularios_e_campos = [
            (ContaForm(sala=self.sala), "saldo_inicial"),
            (EntradaForm(sala=self.sala), "valor"),
            (SaidaForm(sala=self.sala), "valor"),
            (CompraCreditoForm(sala=self.sala), "valor_total"),
        ]

        for formulario, nome_campo in formularios_e_campos:
            with self.subTest(campo=nome_campo):
                self.assertEqual(
                    formulario.fields[nome_campo].widget.attrs["inputmode"],
                    "decimal",
                )

    def test_quantidade_de_parcelas_abre_teclado_numerico(self):
        formulario = CompraCreditoForm(sala=self.sala)

        self.assertEqual(
            formulario.fields["quantidade_parcelas"].widget.attrs["inputmode"],
            "numeric",
        )

    def test_campo_monetario_aceita_formatos_comuns_sem_float(self):
        campo = ValorBrasileiroField(max_digits=12, decimal_places=2)

        self.assertEqual(campo.clean("90"), Decimal("90.00"))
        self.assertEqual(campo.clean("90,00"), Decimal("90.00"))
        self.assertEqual(campo.clean("90.00"), Decimal("90.00"))
        self.assertEqual(campo.clean("R$ 1.234,56"), Decimal("1234.56"))

    def test_campos_financeiros_usam_componente_monetario(self):
        formularios_e_campos = [
            (ContaForm(sala=self.sala), "saldo_inicial"),
            (EntradaForm(sala=self.sala), "valor"),
            (SaidaForm(sala=self.sala), "valor"),
            (CompraCreditoForm(sala=self.sala), "valor_total"),
        ]

        for formulario, nome_campo in formularios_e_campos:
            with self.subTest(campo=nome_campo):
                self.assertIsInstance(
                    formulario.fields[nome_campo], ValorBrasileiroField
                )
                self.assertIn(
                    "data-money-input", formulario.fields[nome_campo].widget.attrs
                )
