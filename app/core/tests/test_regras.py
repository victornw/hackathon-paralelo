import pytest

from app.core import regras
from app.core.arranjo import T_MIN_C, voc_corrigido_v
from app.core.regras import REGRAS, Regra, Veredito, aprovada, avaliar_regras, conferir
from app.docs.gerar import gerar_documentos
from app.schemas import Camada, StatusRegra, StringFV
from app.tracing import listar_passos

APROVADA, REPROVADA = StatusRegra.APROVADA, StatusRegra.REPROVADA
INCERTA, NAO_VERIFICADA = StatusRegra.INCERTA, StatusRegra.NAO_VERIFICADA


def resultado(processo, regra_id):
    (r,) = avaliar_regras(processo, ids=[regra_id])
    return r


class TestRepositorio:
    def test_tem_r01_a_r08_em_ordem(self):
        assert [r.id for r in REGRAS] == [f"R0{i}" for i in range(1, 9)]

    def test_conferir_cobre_todas_com_fonte_e_mensagem(self, confirmado):
        resultados = conferir(confirmado)
        assert [r.regra_id for r in resultados] == [r.id for r in REGRAS]
        assert all(r.fonte_norma and r.mensagem for r in resultados)

    def test_camadas(self):
        camadas = {r.id: r.camada for r in REGRAS}
        assert {camadas[i] for i in ("R01", "R02", "R03", "R04")} == {Camada.TECNICA}
        assert {camadas[i] for i in ("R05", "R06", "R07", "R08")} == {
            Camada.DISTRIBUIDORA
        }

    def test_criterios_ainda_nao_validados_por_engenheiro(self):
        a_validar = {r.id for r in REGRAS if r.a_validar}
        assert a_validar == {"R02", "R03"}

    def test_conferir_registra_passo_de_trace(self, confirmado):
        conferir(confirmado)
        (passo,) = listar_passos(confirmado.id)
        assert passo.passo == "conferir"
        assert passo.erro is None

    def test_regra_nao_pode_devolver_nao_verificada(self):
        with pytest.raises(ValueError):
            Veredito(NAO_VERIFICADA, "x")

    def test_ids_desconhecidos_sao_erro_de_programacao(self, processo):
        with pytest.raises(ValueError):
            avaliar_regras(processo, ids=["R99"])


class TestForaDoMvp:
    @pytest.mark.parametrize(
        "regra_id, fonte",
        [("R06", "Cemig"), ("R07", "Tabela 4"), ("R08", "Anexo G")],
    )
    def test_r06_a_r08_ficam_nao_verificadas_com_a_fonte_da_spec(
        self, processo, regra_id, fonte
    ):
        r = resultado(processo, regra_id)
        assert r.status == NAO_VERIFICADA
        assert fonte in r.fonte_norma
        assert "MVP" in r.mensagem or "fase 2" in r.mensagem


class TestPoliticaDeQuatroEstados:
    def regra_instrumentada(self, processo, monkeypatch):
        chamadas = []

        def avaliar(v):
            chamadas.append(v)
            return aprovada("ok")

        regra = Regra(
            "RX", "teste", Camada.TECNICA, "teste", False, ("bitola_ca_mm2",), avaliar
        )
        monkeypatch.setattr(regras, "REGRAS", (regra,))
        return regra, chamadas

    def test_entrada_ausente_vira_incerta_sem_chamar_a_regra(
        self, processo, monkeypatch
    ):
        _, chamadas = self.regra_instrumentada(processo, monkeypatch)
        (r,) = avaliar_regras(processo)
        assert r.status == INCERTA
        assert "bitola do cabo CA" in r.mensagem
        assert chamadas == []

    def test_com_a_entrada_presente_a_regra_roda(self, processo, monkeypatch):
        _, chamadas = self.regra_instrumentada(processo, monkeypatch)
        processo.visita.bitola_ca_mm2 = 4
        (r,) = avaliar_regras(processo)
        assert (r.status, chamadas) == (APROVADA, [{"bitola_ca_mm2": 4}])
        assert r.valores == {"bitola_ca_mm2": 4}

    def test_excecao_na_regra_vira_incerta_nunca_aprovada(self, processo, monkeypatch):
        def quebra(v):
            raise ZeroDivisionError("boom")

        regra = Regra("RX", "t", Camada.TECNICA, "t", False, ("uc",), quebra)
        monkeypatch.setattr(regras, "REGRAS", (regra,))
        (r,) = avaliar_regras(processo)
        assert r.status == INCERTA
        assert "Erro interno" in r.mensagem
        assert r.valores == {"uc": "7000123456"}

    def test_regra_que_nao_devolve_veredito_vira_incerta(self, processo, monkeypatch):
        regra = Regra(
            "RX", "t", Camada.TECNICA, "t", False, ("uc",), lambda v: "aprovada"
        )
        monkeypatch.setattr(regras, "REGRAS", (regra,))
        (r,) = avaliar_regras(processo)
        assert r.status == INCERTA

    def test_valor_sugerido_aprovado_vira_incerta(self, processo):
        r = resultado(processo, "R03")  # strings do exemplo estão sugeridas
        assert r.status == INCERTA
        assert "sugerido" in r.mensagem
        assert "259" in r.mensagem  # a conta da regra continua visível

    def test_strings_confirmadas_ainda_dependem_da_premissa_termica(self, confirmado):
        assert resultado(confirmado, "R03").status == INCERTA

    def test_valor_sugerido_reprovado_continua_reprovado(self, confirmado):
        confirmado.kit.strings = [StringFV(mppt=1, modulos_em_serie=20, sugerida=True)]
        assert resultado(confirmado, "R03").status == REPROVADA

    @pytest.mark.parametrize(
        "regra_id, apagar",
        [
            ("R02", lambda p: setattr(p.visita, "bitola_ca_mm2", None)),
            ("R02", lambda p: setattr(p.visita, "disjuntor_ca_a", None)),
            ("R03", lambda p: setattr(p.kit.modulo, "coef_temp_voc_pct_c", None)),
            ("R03", lambda p: setattr(p.kit, "strings", [])),
            ("R03", lambda p: setattr(p, "kit", None)),
            ("R04", lambda p: setattr(p, "kit", None)),
            ("R05", lambda p: setattr(p.kit.inversor, "certificado_inmetro", None)),
            ("R05", lambda p: setattr(p.kit.inversor, "certificado_inmetro", "  ")),
            ("R01", lambda p: setattr(p, "documentos", [])),
        ],
    )
    def test_dado_ausente_nunca_aprova(self, com_documentos, regra_id, apagar):
        apagar(com_documentos)
        assert resultado(com_documentos, regra_id).status == INCERTA

    def test_valores_trazem_as_entradas_usadas(self, confirmado):
        r = resultado(confirmado, "R02")
        assert r.valores["corrente_saida_a"] == 22.7
        assert r.valores["disjuntor_ca_a"] == 25
        assert r.valores["bitola_ca_mm2"] == 4
        assert r.valores["capacidade_cabo_a"] == 32


class TestR02DisjuntorCa:
    def test_sem_bitola_fica_incerta_por_politica(self, processo):
        assert resultado(processo, "R02").status == INCERTA

    def test_dentro_da_faixa_ainda_depende_da_validacao_da_tabela(self, confirmado):
        assert resultado(confirmado, "R02").status == INCERTA

    def test_disjuntor_igual_a_corrente_reprova(self, confirmado):
        confirmado.visita.disjuntor_ca_a = confirmado.kit.inversor.corrente_max_saida_a
        r = resultado(confirmado, "R02")
        assert r.status == REPROVADA
        assert "22,7 A" in r.mensagem

    def test_disjuntor_abaixo_da_corrente_reprova(self, confirmado):
        confirmado.visita.disjuntor_ca_a = 20
        assert resultado(confirmado, "R02").status == REPROVADA

    def test_disjuntor_igual_a_capacidade_do_cabo_reprova(self, confirmado):
        confirmado.visita.disjuntor_ca_a = 32
        assert resultado(confirmado, "R02").status == REPROVADA

    def test_cabo_subdimensionado_reprova_e_cita_a_bitola(self, confirmado):
        confirmado.visita.bitola_ca_mm2 = 2.5
        r = resultado(confirmado, "R02")
        assert r.status == REPROVADA
        assert "2,5 mm²" in r.mensagem

    def test_bitola_fora_da_tabela_fica_incerta(self, confirmado):
        confirmado.visita.bitola_ca_mm2 = 35
        assert resultado(confirmado, "R02").status == INCERTA


class TestR03TensaoDasStrings:
    def kit_com_limite(self, confirmado, fator):
        kit = confirmado.kit
        kit.strings = [StringFV(mppt=1, modulos_em_serie=5)]
        tensao = 5 * voc_corrigido_v(kit.modulo.voc_v, kit.modulo.coef_temp_voc_pct_c)
        kit.inversor.tensao_max_cc_v = tensao * fator
        return confirmado

    def test_abaixo_do_limite_ainda_depende_da_premissa_termica(self, confirmado):
        assert resultado(self.kit_com_limite(confirmado, 1.01), "R03").status == INCERTA

    def test_um_por_cento_acima_do_limite_reprova(self, confirmado):
        assert (
            resultado(self.kit_com_limite(confirmado, 0.99), "R03").status == REPROVADA
        )

    def test_no_limite_ainda_depende_da_premissa_termica(self, confirmado):
        assert resultado(self.kit_com_limite(confirmado, 1.0), "R03").status == INCERTA

    def test_mensagem_avisa_que_o_coeficiente_e_fixo_e_a_validar(self, confirmado):
        r = resultado(confirmado, "R03")
        assert "a validar com engenheiro" in r.mensagem
        assert r.a_validar
        assert r.valores["temperatura_minima_c"] == T_MIN_C

    def test_usa_a_pior_string_e_nomeia_o_mppt_que_falha(self, confirmado):
        confirmado.kit.strings = [
            StringFV(mppt=1, modulos_em_serie=5),
            StringFV(mppt=2, modulos_em_serie=12),
        ]
        r = resultado(confirmado, "R03")
        assert r.status == REPROVADA
        assert "MPPT 2" in r.mensagem and "MPPT 1" not in r.mensagem
        assert r.valores["modulos_em_serie"] == 12


class TestR04PotenciaCc:
    def test_igual_ao_limite_aprova(self, confirmado):
        confirmado.kit.inversor.potencia_max_cc_w = confirmado.kit.potencia_total_wp
        assert resultado(confirmado, "R04").status == APROVADA

    def test_um_watt_acima_reprova(self, confirmado):
        confirmado.kit.inversor.potencia_max_cc_w = confirmado.kit.potencia_total_wp - 1
        assert resultado(confirmado, "R04").status == REPROVADA

    def test_abaixo_do_limite_aprova(self, confirmado):
        assert resultado(confirmado, "R04").status == APROVADA


class TestR05Inmetro:
    def test_numero_preenchido_nao_comprova_certificacao(self, confirmado):
        r = resultado(confirmado, "R05")
        assert r.status == INCERTA
        assert "não foi checado no registro" in r.mensagem

    def test_inversor_acima_de_75_kw_fica_incerta(self, confirmado):
        confirmado.kit.inversor.potencia_nominal_w = 80_000
        assert resultado(confirmado, "R05").status == INCERTA

    def test_exatamente_75_kw_ainda_exige_certificado(self, confirmado):
        confirmado.kit.inversor.potencia_nominal_w = 75_000
        assert resultado(confirmado, "R05").status == INCERTA


class TestR01Coerencia:
    def test_documentos_gerados_do_mesmo_processo_sao_coerentes(self, com_documentos):
        r = resultado(com_documentos, "R01")
        assert r.status == APROVADA, r.mensagem

    def test_sem_documentos_fica_incerta(self, confirmado):
        r = resultado(confirmado, "R01")
        assert r.status == INCERTA
        assert "documentos gerados" in r.mensagem

    def substituir(self, processo, tipo, outro):
        """Troca o documento `tipo` pelo gerado a partir de `outro`."""
        outro.id = "proc-alterado"
        novos = {(d.tipo, d.formato): d for d in gerar_documentos(outro)}
        processo.documentos = [
            novos[(d.tipo, d.formato)] if d.tipo == tipo else d
            for d in processo.documentos
        ]

    @pytest.mark.parametrize("tipo", ["solicitacao_orcamento", "memorial", "unifilar"])
    def test_titular_diferente_num_documento_reprova_e_nomeia_o_documento(
        self, com_documentos, tipo
    ):
        alterado = com_documentos.model_copy(deep=True)
        alterado.campos["titular"].valor = "JOAO OUTRO DE SOUZA"
        self.substituir(com_documentos, tipo, alterado)
        r = resultado(com_documentos, "R01")
        assert r.status == REPROVADA
        assert "MARIA SINTETICA DA SILVA" in r.mensagem
        nome = {
            "solicitacao_orcamento": "Anexo A",
            "memorial": "Memorial",
            "unifilar": "Unifilar",
        }[tipo]
        assert nome in r.mensagem

    def test_disjuntor_ca_diferente_no_memorial_reprova(self, com_documentos):
        alterado = com_documentos.model_copy(deep=True)
        alterado.visita.disjuntor_ca_a = 32
        self.substituir(com_documentos, "memorial", alterado)
        r = resultado(com_documentos, "R01")
        assert r.status == REPROVADA
        assert "disjuntor CA (25)" in r.mensagem

    def test_modelo_do_inversor_diferente_no_unifilar_reprova(self, com_documentos):
        alterado = com_documentos.model_copy(deep=True)
        alterado.kit.inversor.modelo = "OUTRO-INV-9K"
        self.substituir(com_documentos, "unifilar", alterado)
        assert resultado(com_documentos, "R01").status == REPROVADA

    def test_quantidade_de_modulos_diferente_reprova(self, com_documentos):
        alterado = com_documentos.model_copy(deep=True)
        alterado.kit.qtd_modulos = 12
        self.substituir(com_documentos, "solicitacao_orcamento", alterado)
        assert resultado(com_documentos, "R01").status == REPROVADA

    def test_dado_do_processo_editado_depois_de_gerar_reprova(self, com_documentos):
        com_documentos.visita.disjuntor_ca_a = 32
        assert resultado(com_documentos, "R01").status == REPROVADA

    def test_disjuntor_do_padrao_igual_nao_mascara_divergencia_do_disjuntor_ca(
        self, com_documentos
    ):
        com_documentos.visita.disjuntor_ca_a = 50  # o padrão imprime "50 A"
        assert resultado(com_documentos, "R01").status == REPROVADA

    def test_arquivo_ausente_fica_incerta(self, com_documentos):
        for d in com_documentos.documentos:
            if d.tipo == "memorial":
                d.caminho += ".sumiu"
        r = resultado(com_documentos, "R01")
        assert r.status == INCERTA
        assert "Memorial" in r.mensagem

    def test_divergencia_pesa_mais_que_documento_ilegivel(self, com_documentos):
        for d in com_documentos.documentos:
            if d.tipo == "memorial":
                d.caminho += ".sumiu"
        com_documentos.campos["uc"].valor = "9999999999"
        assert resultado(com_documentos, "R01").status == REPROVADA

    def test_unifilar_sem_pdf_legivel_usa_o_svg(self, com_documentos):
        com_documentos.documentos = [
            d
            for d in com_documentos.documentos
            if not (d.tipo == "unifilar" and d.formato == "pdf")
        ]
        assert resultado(com_documentos, "R01").status == APROVADA
