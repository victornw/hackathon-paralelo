import pytest

from app.core.arranjo import (
    CABO_IZ_A,
    DISJUNTORES_A,
    bitola_por_tabela,
    disjuntor_por_tabela,
    propor_strings,
    verificar_arranjo,
    voc_corrigido_v,
)
from app.schemas import DadosVisita, Kit, StatusRegra, StringFV
from app.tracing import listar_passos


@pytest.fixture
def kit(processo) -> Kit:
    return processo.kit.model_copy(deep=True, update={"strings": []})


def status(resultados) -> dict[str, StatusRegra]:
    return {r.regra_id: r.status for r in resultados}


class TestTabelas:
    @pytest.mark.parametrize(
        "corrente, esperado",
        [(22.7, 25), (25, 32), (9.9, 10), (62.9, 63), (63, None), (80, None)],
    )
    def test_disjuntor_e_o_menor_estritamente_acima_da_corrente(
        self, corrente, esperado
    ):
        assert disjuntor_por_tabela(corrente) == esperado

    @pytest.mark.parametrize(
        "disjuntor, esperado",
        [(25, 4), (32, 6), (24, 4), (16, 1.5), (17.5, 2.5), (101, None)],
    )
    def test_bitola_e_a_menor_com_capacidade_acima_do_disjuntor(
        self, disjuntor, esperado
    ):
        assert bitola_por_tabela(disjuntor) == esperado

    def test_tabelas_estao_em_ordem_crescente(self):
        assert list(DISJUNTORES_A) == sorted(DISJUNTORES_A)
        capacidades = [CABO_IZ_A[b] for b in sorted(CABO_IZ_A)]
        assert capacidades == sorted(capacidades)

    def test_voc_a_frio_sobe_com_coeficiente_negativo(self):
        assert voc_corrigido_v(50, -0.3) == pytest.approx(50 * 1.045)


class TestProporStrings:
    def test_uma_string_no_mppt_1_quando_cabe(self, kit):
        strings = propor_strings(kit)
        assert [(s.mppt, s.modulos_em_serie, s.sugerida) for s in strings] == [
            (1, 10, True)
        ]

    def test_divide_entre_dois_mppts_quando_uma_string_nao_cabe(self, kit):
        kit.qtd_modulos = 12
        strings = propor_strings(kit)
        assert [(s.mppt, s.modulos_em_serie) for s in strings] == [(1, 6), (2, 6)]
        assert all(s.sugerida for s in strings)

    def test_divisao_impar_fica_balanceada(self, kit):
        kit.qtd_modulos = 13
        assert [s.modulos_em_serie for s in propor_strings(kit)] == [7, 6]

    def test_nao_divide_se_o_inversor_tem_um_mppt(self, kit):
        kit.qtd_modulos = 12
        kit.inversor.num_mppt = 1
        assert propor_strings(kit) == []

    def test_devolve_vazio_quando_nada_cabe(self, kit):
        kit.inversor.tensao_max_cc_v = 100
        assert propor_strings(kit) == []

    def test_sem_coeficiente_de_temperatura_nao_inventa(self, kit):
        kit.modulo.coef_temp_voc_pct_c = None
        assert propor_strings(kit) == []

    def test_exatamente_no_limite_ainda_cabe(self, kit):
        kit.inversor.tensao_max_cc_v = 10 * voc_corrigido_v(
            kit.modulo.voc_v, kit.modulo.coef_temp_voc_pct_c
        )
        assert [s.modulos_em_serie for s in propor_strings(kit)] == [10]

    def test_microinversor_liga_cada_modulo_sozinho(self, kit):
        kit.inversor.microinversor = True
        strings = propor_strings(kit)
        assert [(s.mppt, s.modulos_em_serie, s.sugerida) for s in strings] == [
            (1, 1, True)
        ]


class TestVerificarArranjo:
    def test_propoe_strings_sugeridas_e_escolhe_disjuntor_por_tabela(self, kit):
        novo_kit, nova_visita, _ = verificar_arranjo(kit, DadosVisita())
        assert novo_kit.strings and all(s.sugerida for s in novo_kit.strings)
        assert nova_visita.disjuntor_ca_a == 25

    def test_nao_altera_os_argumentos(self, kit):
        visita = DadosVisita()
        verificar_arranjo(kit, visita)
        assert kit.strings == []
        assert visita.disjuntor_ca_a is None

    def test_mantem_strings_informadas_e_disjuntor_e_bitola_dados(self, kit):
        kit.strings = [StringFV(mppt=1, modulos_em_serie=10)]
        visita = DadosVisita(disjuntor_ca_a=32, bitola_ca_mm2=6)
        novo_kit, nova_visita, _ = verificar_arranjo(kit, visita)
        assert novo_kit.strings == kit.strings
        assert (nova_visita.disjuntor_ca_a, nova_visita.bitola_ca_mm2) == (32, 6)

    def test_nunca_escreve_bitola(self, kit):
        _, nova_visita, _ = verificar_arranjo(kit, DadosVisita())
        assert nova_visita.bitola_ca_mm2 is None

    def test_devolve_r03_e_r04(self, kit):
        _, _, resultados = verificar_arranjo(kit, DadosVisita())
        assert [r.regra_id for r in resultados] == ["R03", "R04"]

    def test_string_sugerida_deixa_r03_incerta_e_r04_aprovada(self, kit):
        _, _, resultados = verificar_arranjo(kit, DadosVisita())
        assert status(resultados) == {
            "R03": StatusRegra.INCERTA,
            "R04": StatusRegra.APROVADA,
        }

    def test_strings_informadas_nao_confirmam_premissa_termica(self, kit):
        kit.strings = propor_strings(kit)
        for s in kit.strings:
            s.sugerida = False
        _, _, resultados = verificar_arranjo(kit, DadosVisita())
        assert status(resultados)["R03"] == StatusRegra.INCERTA

    def test_sem_configuracao_possivel_r03_fica_incerta(self, kit):
        kit.inversor.tensao_max_cc_v = 100
        novo_kit, _, resultados = verificar_arranjo(kit, DadosVisita())
        assert novo_kit.strings == []
        assert status(resultados)["R03"] == StatusRegra.INCERTA

    def test_corrente_acima_da_tabela_deixa_disjuntor_vazio(self, kit):
        kit.inversor.corrente_max_saida_a = 70
        _, nova_visita, _ = verificar_arranjo(kit, DadosVisita())
        assert nova_visita.disjuntor_ca_a is None

    def test_grava_passo_de_trace(self, kit):
        verificar_arranjo(kit, DadosVisita())
        passos = listar_passos("sem_processo")
        assert [p.passo for p in passos] == ["verificar_arranjo"]
        assert "disjuntor CA 25" in passos[0].decisao
