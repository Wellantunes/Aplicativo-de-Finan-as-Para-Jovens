import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contas.models import Conta
from entradas.models import ConfiguracaoDizimo, Entrada, FormaCalculoDizimo
from saidas.models import Saida
from salas.models import MembroSala, Sala

from .espacos import CHAVE_ESPACO_SESSAO, ESPACO_INDIVIDUAL, ESPACO_SALA
from .atalhos import CATALOGOS_SIMBOLOS, SIMBOLO_PADRAO, SIMBOLOS_ATALHO
from .models import AtalhoLancamento


class AtalhosLancamentoTests(TestCase):
    def setUp(self):
        Usuario = get_user_model()
        self.usuario = Usuario.objects.create_user(
            username="ana",
            avatar_concluido=True,
            configuracao_inicial_concluida=True,
        )
        self.parceiro = Usuario.objects.create_user(
            username="leo",
            avatar_concluido=True,
            configuracao_inicial_concluida=True,
        )
        self.externo = Usuario.objects.create_user(
            username="bia",
            avatar_concluido=True,
            configuracao_inicial_concluida=True,
        )
        self.conta = Conta.objects.create(
            proprietario_usuario=self.usuario,
            autor=self.usuario,
            titular=self.usuario,
            tipo=Conta.Tipo.DINHEIRO,
            nome="Conta pessoal",
            saldo_inicial=Decimal("100.00"),
            data_saldo_inicial=date(2026, 1, 1),
        )
        self.conta_externa = Conta.objects.create(
            proprietario_usuario=self.externo,
            autor=self.externo,
            titular=self.externo,
            tipo=Conta.Tipo.DINHEIRO,
            nome="Conta externa",
            saldo_inicial=Decimal("10.00"),
            data_saldo_inicial=date(2026, 1, 1),
        )
        self.atalho_saida = AtalhoLancamento.objects.create(
            proprietario_usuario=self.usuario,
            nome="Mercado",
            tipo=AtalhoLancamento.Tipo.SAIDA,
            simbolo="saida_supermercado",
            categoria="alimentacao",
            conta_padrao=self.conta,
            ordem=1,
        )
        self.atalho_entrada = AtalhoLancamento.objects.create(
            proprietario_usuario=self.usuario,
            nome="Salário",
            tipo=AtalhoLancamento.Tipo.ENTRADA,
            simbolo="entrada_salario",
            categoria="salario",
            conta_padrao=self.conta,
            ordem=1,
        )
        self.client.force_login(self.usuario)
        self._ativar_espaco(ESPACO_INDIVIDUAL)

    def _ativar_espaco(self, espaco):
        sessao = self.client.session
        sessao[CHAVE_ESPACO_SESSAO] = espaco
        sessao.save()

    def _dados_rapidos(self, *, valor="25,50", data=None, chave=None):
        return {
            "chave_formulario": str(chave or uuid.uuid4()),
            "mes_consulta": "2026-09",
            "valor": valor,
            "data": (data or timezone.localdate()).isoformat(),
            "observacao": "Registro pelo atalho",
        }

    def test_criar_atalho_nao_movimenta_dinheiro(self):
        saldo_antes = self.conta.saldo_atual
        response = self.client.post(
            reverse("core:criar_atalho"),
            {
                "nome": "Faculdade",
                "tipo": "saida",
                "simbolo": "saida_estudos",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AtalhoLancamento.objects.filter(nome="Faculdade").exists())
        self.assertFalse(Entrada.objects.exists())
        self.assertFalse(Saida.objects.exists())
        self.assertEqual(self.conta.saldo_atual, saldo_antes)

    def test_catalogos_separam_entrada_e_saida_com_arquivos_validos(self):
        antigos = {
            "generico", "alimentacao", "carteira", "entrada",
            "coracao", "moedas", "calendario", "lista",
        }

        self.assertEqual(len(CATALOGOS_SIMBOLOS["entrada"]), 7)
        self.assertEqual(len(CATALOGOS_SIMBOLOS["saida"]), 54)
        self.assertEqual(len(SIMBOLOS_ATALHO), 61)
        self.assertTrue(antigos.isdisjoint(SIMBOLOS_ATALHO))
        self.assertTrue(
            all(simbolo.startswith("entrada_") for simbolo in CATALOGOS_SIMBOLOS["entrada"])
        )
        self.assertTrue(
            all(simbolo.startswith("saida_") for simbolo in CATALOGOS_SIMBOLOS["saida"])
        )
        for dados in SIMBOLOS_ATALHO.values():
            caminho = Path(settings.BASE_DIR, "static", dados["arquivo"])
            self.assertTrue(caminho.is_file(), caminho)

    def test_formulario_separa_simbolos_sem_cor_de_destaque(self):
        response_saida = self.client.get(
            reverse("core:criar_atalho"),
            {"tipo": "saida"},
        )
        response_entrada = self.client.get(
            reverse("core:criar_atalho"),
            {"tipo": "entrada"},
        )

        self.assertEqual(len(response_saida.context["form"].fields["simbolo"].choices), 54)
        self.assertEqual(len(response_entrada.context["form"].fields["simbolo"].choices), 7)
        self.assertNotIn("tipo", response_saida.context["form"].fields)
        self.assertNotIn("cor", response_saida.context["form"].fields)
        self.assertNotContains(response_saida, "Cor de destaque")
        self.assertContains(response_saida, 'value="saida_supermercado"')
        self.assertNotContains(response_saida, 'value="entrada_salario"')
        self.assertContains(response_entrada, 'value="entrada_salario"')
        self.assertNotContains(response_entrada, 'value="saida_supermercado"')
        self.assertNotContains(response_entrada, 'name="tipo"')

    def test_novo_simbolo_pode_ser_selecionado_e_salvo(self):
        response = self.client.post(
            reverse("core:criar_atalho") + "?tipo=saida&mes=2026-10",
            {"nome": "Presente", "tipo": "saida", "simbolo": "saida_presentes"},
        )

        self.assertRedirects(
            response,
            reverse("core:lancamentos") + "?tipo=saida&mes=2026-10",
        )
        item = AtalhoLancamento.objects.get(nome="Presente")
        self.assertEqual(item.simbolo, "saida_presentes")
        self.assertEqual(
            item.caminho_simbolo,
            "dropduo/item-icons/saida/39_presentes.png",
        )

    def test_icones_de_bonus_e_renda_extra_usam_tipo_extra(self):
        for simbolo in ("entrada_bonus", "entrada_renda_extra"):
            response = self.client.post(
                reverse("core:criar_atalho") + "?tipo=entrada",
                {"nome": simbolo, "tipo": "entrada", "simbolo": simbolo},
            )
            self.assertEqual(response.status_code, 302)

        categorias = set(
            AtalhoLancamento.objects.filter(
                simbolo__in=["entrada_bonus", "entrada_renda_extra"]
            ).values_list("categoria", flat=True)
        )
        self.assertEqual(categorias, {"extra"})

    def test_backend_rejeita_simbolo_de_outro_tipo(self):
        response = self.client.post(
            reverse("core:criar_atalho") + "?tipo=entrada",
            {
                "nome": "Entrada inválida",
                "simbolo": "saida_supermercado",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Escolha um símbolo compatível com o tipo do item.")
        self.assertFalse(AtalhoLancamento.objects.filter(nome="Entrada inválida").exists())

        self.atalho_entrada.simbolo = "saida_supermercado"
        with self.assertRaises(ValidationError):
            self.atalho_entrada.full_clean()

    def test_contexto_define_tipo_e_ignora_tipo_adulterado(self):
        response = self.client.post(
            reverse("core:criar_atalho") + "?tipo=saida",
            {
                "nome": "Mercado seguro",
                "tipo": "entrada",
                "simbolo": "saida_supermercado",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            AtalhoLancamento.objects.get(nome="Mercado seguro").tipo,
            AtalhoLancamento.Tipo.SAIDA,
        )

    def test_edicao_preserva_tipo_original_mesmo_com_url_adulterada(self):
        response = self.client.post(
            reverse("core:editar_atalho", args=[self.atalho_entrada.pk]) + "?tipo=saida",
            {
                "nome": "Salário atualizado",
                "tipo": "saida",
                "simbolo": "entrada_salario",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.atalho_entrada.refresh_from_db()
        self.assertEqual(self.atalho_entrada.tipo, AtalhoLancamento.Tipo.ENTRADA)

    def test_lancamentos_entrada_abre_o_mesmo_formulario_rapido_do_vale(self):
        response = self.client.get(
            reverse("core:lancamentos"),
            {"tipo": "entrada", "mes": "2026-10"},
        )
        destino = reverse("core:registrar_vale") + "?mes=2026-10"

        self.assertContains(response, "Vale-alimentação")
        self.assertContains(response, f'href="{destino}"')
        self.assertContains(response, "dropduo/icons/talheres.png")

    def test_registro_rapido_do_vale_e_explicito_separado_e_idempotente(self):
        url = reverse("core:registrar_vale") + "?mes=2026-10"
        chave = uuid.uuid4()
        dados = {
            "chave_formulario": str(chave),
            "mes_consulta": "2026-10",
            "valor": "280,00",
            "descricao": "Vale iFood",
            "data": timezone.localdate().isoformat(),
        }

        primeira = self.client.post(url, dados)
        segunda = self.client.post(url, dados)

        self.assertEqual(primeira.status_code, 302)
        self.assertEqual(segunda.status_code, 302)
        self.assertEqual(Entrada.objects.count(), 1)
        entrada = Entrada.objects.get()
        self.assertEqual(entrada.tipo, "vale_alimentacao")
        self.assertEqual(entrada.categoria_atalho, "vale_alimentacao")
        self.assertEqual(entrada.descricao, "Vale iFood")
        self.assertEqual(entrada.valor, Decimal("280.00"))
        self.assertIsNone(entrada.conta_destino)
        self.assertIsNone(entrada.atalho)
        self.assertFalse(AtalhoLancamento.objects.filter(nome="Vale-alimentação").exists())

    def test_vale_futuro_vira_previsao_e_respeita_sala_ativa(self):
        sala = Sala.objects.create(
            nome="Casa",
            orcamento_mensal=Decimal("2000.00"),
            criado_por=self.usuario,
        )
        MembroSala.objects.create(sala=sala, usuario=self.usuario)
        self._ativar_espaco(ESPACO_SALA)
        data_futura = timezone.localdate() + timedelta(days=5)

        response = self.client.post(
            reverse("core:registrar_vale"),
            {
                "chave_formulario": str(uuid.uuid4()),
                "mes_consulta": data_futura.strftime("%Y-%m"),
                "valor": "90,00",
                "descricao": "Vale futuro",
                "data": data_futura.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 302)
        entrada = Entrada.objects.get()
        self.assertEqual(entrada.sala, sala)
        self.assertIsNone(entrada.proprietario_usuario)
        self.assertEqual(entrada.situacao, Entrada.Situacao.A_RECEBER)
        self.assertIsNone(entrada.data)
        self.assertEqual(entrada.data_prevista, data_futura)

    def test_editar_e_recarregar_preserva_simbolo_do_tipo(self):
        response = self.client.post(
            reverse("core:editar_atalho", args=[self.atalho_entrada.pk]),
            {
                "nome": self.atalho_entrada.nome,
                "tipo": "entrada",
                "simbolo": "entrada_investimento",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.atalho_entrada.refresh_from_db()
        self.assertEqual(self.atalho_entrada.simbolo, "entrada_investimento")
        self.assertEqual(
            self.atalho_entrada.caminho_simbolo,
            "dropduo/item-icons/entrada/04_investimento.png",
        )

    def test_registro_rapido_de_saida_aceita_formato_brasileiro(self):
        response = self.client.post(
            reverse("core:registrar_atalho", args=[self.atalho_saida.pk]),
            self._dados_rapidos(valor="1.234,56"),
        )
        self.assertEqual(response.status_code, 302)
        saida = Saida.objects.get()
        self.assertEqual(saida.valor, Decimal("1234.56"))
        self.assertEqual(saida.data_pagamento, timezone.localdate())
        self.assertEqual(saida.observacao, "Registro pelo atalho")
        self.assertEqual(saida.categoria_atalho, "alimentacao")
        self.assertEqual(saida.atalho, self.atalho_saida)
        self.assertIsNone(saida.conta)
        self.assertEqual(self.conta.saldo_atual, Decimal("100.00"))

    def test_registro_rapido_de_entrada_e_idempotente(self):
        chave = uuid.uuid4()
        dados = self._dados_rapidos(valor="200,00", chave=chave)
        url = reverse("core:registrar_atalho", args=[self.atalho_entrada.pk])
        self.client.post(url, dados)
        self.client.post(url, dados)
        self.assertEqual(Entrada.objects.count(), 1)
        entrada = Entrada.objects.get()
        self.assertEqual(entrada.valor, Decimal("200.00"))
        self.assertIsNone(entrada.conta_destino)
        self.assertEqual(self.conta.saldo_atual, Decimal("100.00"))

    def test_registros_rapidos_pessoais_respeitam_preferencia_de_compartilhamento(self):
        sala = Sala.objects.create(
            nome="Casa compartilhada",
            orcamento_mensal=Decimal("2000.00"),
            criado_por=self.usuario,
        )
        MembroSala.objects.create(sala=sala, usuario=self.usuario)
        self.usuario.compartilhar_novos_lancamentos = True
        self.usuario.save(update_fields=["compartilhar_novos_lancamentos"])

        self.client.post(
            reverse("core:registrar_atalho", args=[self.atalho_entrada.pk]),
            self._dados_rapidos(valor="200,00"),
        )
        self.client.post(
            reverse("core:registrar_atalho", args=[self.atalho_saida.pk]),
            self._dados_rapidos(valor="80,00"),
        )

        entrada = Entrada.objects.get()
        saida = Saida.objects.get()
        self.assertEqual(entrada.proprietario_usuario, self.usuario)
        self.assertEqual(saida.proprietario_usuario, self.usuario)
        self.assertEqual(entrada.sala_compartilhada, sala)
        self.assertEqual(saida.sala_compartilhada, sala)
        self.assertIsNone(entrada.conta_destino)
        self.assertIsNone(saida.conta)

    def test_registro_rapido_pessoal_fica_privado_sem_preferencia(self):
        sala = Sala.objects.create(
            nome="Casa privada",
            orcamento_mensal=Decimal("2000.00"),
            criado_por=self.usuario,
        )
        MembroSala.objects.create(sala=sala, usuario=self.usuario)

        self.client.post(
            reverse("core:registrar_atalho", args=[self.atalho_entrada.pk]),
            self._dados_rapidos(),
        )

        self.assertIsNone(Entrada.objects.get().sala_compartilhada)

    def test_data_inicial_e_hoje_mes_consultado_nao_a_substitui(self):
        response = self.client.get(
            reverse("core:registrar_atalho", args=[self.atalho_entrada.pk]),
            {"mes": "2026-09"},
        )
        self.assertEqual(response.context["form"].initial["data"], timezone.localdate())
        self.assertEqual(response.context["form"].initial["mes_consulta"], "2026-09")

    def test_data_manual_e_preservada_e_data_futura_vira_previsao(self):
        url = reverse("core:registrar_atalho", args=[self.atalho_entrada.pk])
        data_passada = timezone.localdate() - timedelta(days=8)
        self.client.post(url, self._dados_rapidos(data=data_passada))
        self.assertEqual(Entrada.objects.get().data, data_passada)

        response = self.client.post(
            url,
            self._dados_rapidos(data=timezone.localdate() + timedelta(days=1)),
        )
        self.assertEqual(response.status_code, 302)
        prevista = Entrada.objects.get(situacao=Entrada.Situacao.A_RECEBER)
        self.assertIsNone(prevista.data)
        self.assertEqual(prevista.data_prevista, timezone.localdate() + timedelta(days=1))
        self.assertEqual(Entrada.objects.count(), 2)

    def test_saida_futura_vira_conta_a_pagar_sem_pagamento_automatico(self):
        data_futura = timezone.localdate() + timedelta(days=30)

        response = self.client.post(
            reverse("core:registrar_atalho", args=[self.atalho_saida.pk]),
            self._dados_rapidos(data=data_futura),
        )

        self.assertEqual(response.status_code, 302)
        saida = Saida.objects.get()
        self.assertEqual(saida.situacao, Saida.Situacao.PENDENTE)
        self.assertEqual(saida.vencimento, data_futura)
        self.assertIsNone(saida.data_pagamento)

    def test_arquivar_preserva_lancamento_e_retira_atalho_da_grade(self):
        self.client.post(
            reverse("core:registrar_atalho", args=[self.atalho_entrada.pk]),
            self._dados_rapidos(),
        )
        self.client.post(
            reverse("core:alternar_arquivo_atalho", args=[self.atalho_entrada.pk])
        )
        self.atalho_entrada.refresh_from_db()
        self.assertTrue(self.atalho_entrada.arquivado)
        self.assertEqual(Entrada.objects.get().atalho, self.atalho_entrada)
        response = self.client.get(reverse("core:lancamentos"), {"tipo": "entrada"})
        self.assertNotIn(self.atalho_entrada, response.context["atalhos"])
        self.assertContains(response, "Itens arquivados")
        self.assertContains(response, "Restaurar")

    def test_editar_padrao_nao_altera_lancamento_existente(self):
        self.client.post(
            reverse("core:registrar_atalho", args=[self.atalho_entrada.pk]),
            self._dados_rapidos(valor="70,00"),
        )
        entrada = Entrada.objects.get()
        self.atalho_entrada.nome = "Novo nome"
        self.atalho_entrada.categoria = "extra"
        self.atalho_entrada.conta_padrao = None
        self.atalho_entrada.save()
        entrada.refresh_from_db()
        self.assertEqual(entrada.descricao, "Salário")
        self.assertEqual(entrada.tipo, "salario")
        self.assertEqual(entrada.categoria_atalho, "salario")
        self.assertIsNone(entrada.conta_destino)
        self.assertEqual(entrada.valor, Decimal("70.00"))

    def test_rejeita_atalho_externo_e_ignora_conta_enviada_manualmente(self):
        atalho_externo = AtalhoLancamento.objects.create(
            proprietario_usuario=self.externo,
            nome="Privado",
            tipo="saida",
            simbolo=SIMBOLO_PADRAO,
            categoria="outros",
        )
        self.assertEqual(
            self.client.get(
                reverse("core:registrar_atalho", args=[atalho_externo.pk])
            ).status_code,
            404,
        )
        response = self.client.post(
            reverse("core:registrar_atalho", args=[self.atalho_saida.pk]),
            {
                **self._dados_rapidos(),
                "conta": self.conta_externa.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(Saida.objects.get().conta)

    def test_atalho_da_sala_e_compartilhado_so_com_membros(self):
        sala = Sala.objects.create(
            nome="Casa",
            orcamento_mensal=Decimal("2000.00"),
            criado_por=self.usuario,
        )
        MembroSala.objects.create(sala=sala, usuario=self.usuario)
        MembroSala.objects.create(sala=sala, usuario=self.parceiro)
        atalho_sala = AtalhoLancamento.objects.create(
            sala=sala,
            nome="Aluguel",
            tipo="saida",
            simbolo="saida_casa",
            categoria="moradia",
        )
        self._ativar_espaco(ESPACO_SALA)
        self.assertContains(self.client.get(reverse("core:lancamentos")), "Aluguel")
        self.client.post(
            reverse("core:registrar_atalho", args=[atalho_sala.pk]),
            self._dados_rapidos(),
        )
        saida_sala = Saida.objects.get(atalho=atalho_sala)
        self.assertEqual(saida_sala.sala, sala)
        self.assertIsNone(saida_sala.proprietario_usuario)
        self.assertIsNone(saida_sala.sala_compartilhada)
        self.client.force_login(self.parceiro)
        self._ativar_espaco(ESPACO_SALA)
        self.assertEqual(
            self.client.get(
                reverse("core:registrar_atalho", args=[atalho_sala.pk])
            ).status_code,
            200,
        )
        self.client.force_login(self.externo)
        self._ativar_espaco(ESPACO_SALA)
        self.assertEqual(
            self.client.get(
                reverse("core:registrar_atalho", args=[atalho_sala.pk])
            ).status_code,
            404,
        )

    def test_nome_dizimos_nao_ativa_calculo_mas_preferencia_e_configuracao_sim(self):
        self.atalho_entrada.nome = "Dízimos"
        self.atalho_entrada.save(update_fields=["nome"])
        url = reverse("core:registrar_atalho", args=[self.atalho_entrada.pk])
        self.client.post(url, self._dados_rapidos(valor="100,00"))
        self.assertEqual(Entrada.objects.get().dizimo_previsto, Decimal("0.00"))

        self.usuario.dizimo_automatico = True
        self.usuario.save(update_fields=["dizimo_automatico"])
        ConfiguracaoDizimo.objects.create(
            proprietario_usuario=self.usuario,
            pessoa=self.usuario,
            tipo_entrada="salario",
            calcular_dizimo=True,
            forma_calculo=FormaCalculoDizimo.PERCENTUAL,
            percentual_dizimo=Decimal("10.00"),
        )
        self.client.post(url, self._dados_rapidos(valor="200,00"))
        self.assertEqual(
            Entrada.objects.order_by("pk").last().dizimo_previsto,
            Decimal("20.00"),
        )
        self.assertFalse(Saida.objects.exists())
