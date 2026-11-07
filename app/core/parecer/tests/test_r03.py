import pytest

from app.core.parecer.r03_strings import avaliar, fator_beta, fator_tabela
from app.schemas import StatusRegra, StringFV


@pytest.fixture
def caso_engenheiro(processo):
    """Caso de teste do parecer: Voc 49,5 V, β -0,27 %/°C, Tmin 10 °C, Vmax 600 V."""
    k = processo.kit
    k.modulo.voc_v, k.modulo.coef_temp_voc_pct_c = 49.5, -0.27
    k.inversor.tensao_max_cc_v = 600
    k.inversor.corrente_max_entrada_a = 20  # corrente fora do foco destes casos
    k.modulo.vmp_v = None  # janela do MPPT fora do foco
    processo.visita.area_concessao = "ceara"
    return processo


def _string(p, n):
    p.kit.strings = [StringFV(mppt=1, modulos_em_serie=n)]
    return avaliar(p)


def test_fator_e_voc_do_parecer():
    assert round(fator_beta(-0.27, 10), 4) == 1.0405
    assert round(49.5 * fator_beta(-0.27, 10), 3) == 51.505


@pytest.mark.parametrize(
    ("n", "tensao", "pct", "status"),
    [
        (10, 515.0, 85.8, StatusRegra.APROVADA),
        (11, 566.6, 94.4, StatusRegra.APROVADA),  # 0,6 ponto abaixo do limiar de alerta
        (12, 618.1, 103.0, StatusRegra.REPROVADA),
    ],
)
def test_casos_do_engenheiro(caso_engenheiro, n, tensao, pct, status):
    r = _string(caso_engenheiro, n)
    assert r.status == status
    assert r.valores["tensao_string_v"] == tensao
    assert r.valores["uso_tensao_max_pct"] == pct
    if n == 11:
        assert not [a for a in r.alertas if "da tensão máxima CC" in a]


def test_exemplo_de_5_modulos_259_8_v(processo):
    processo.visita.area_concessao = "ceara"  # fixture: 49,9 V, β -0,275, 2 x 5
    r = avaliar(processo)
    assert r.status == StatusRegra.APROVADA
    assert r.valores["tensao_string_v"] == 259.8


def test_acima_de_95_alerta(caso_engenheiro):
    caso_engenheiro.kit.inversor.tensao_max_cc_v = 590  # 566,6 / 590 = 96,0%
    r = _string(caso_engenheiro, 11)
    assert r.status == StatusRegra.APROVADA
    assert any("da tensão máxima CC" in a for a in r.alertas)


def test_tabela_sozinha_acima_de_100_so_alerta(caso_engenheiro):
    caso_engenheiro.kit.inversor.tensao_max_cc_v = 570  # datasheet 99,4%; tabela 101,3%
    r = _string(caso_engenheiro, 11)
    assert r.status == StatusRegra.APROVADA
    assert any("tabela de correção" in a for a in r.alertas)


def test_sem_beta_usa_tabela_como_premissa(caso_engenheiro):
    caso_engenheiro.kit.modulo.coef_temp_voc_pct_c = None
    r = _string(caso_engenheiro, 10)  # 10 x 49,5 x 1,06 = 524,7 V
    assert r.status == StatusRegra.APROVADA and r.premissas
    assert _string(caso_engenheiro, 12).status == StatusRegra.REPROVADA  # 629,6 V


def test_fator_da_tabela_por_faixa():
    assert (
        fator_tabela(10) == 1.06
        and fator_tabela(-3) == 1.12
        and fator_tabela(25) == 1.0
    )


def test_tmin_por_area(caso_engenheiro):
    caso_engenheiro.visita.area_concessao = "sao_paulo"
    r = _string(caso_engenheiro, 10)
    assert r.valores["tmin_c"] == -3
    caso_engenheiro.visita.area_concessao = "rj_sul_fluminense"
    r = _string(caso_engenheiro, 10)
    assert r.valores["tmin_c"] == -5 and any("provisória" in p for p in r.premissas)


def test_area_ausente_nao_chuta(caso_engenheiro):
    caso_engenheiro.visita.area_concessao = None
    assert _string(caso_engenheiro, 10).status == StatusRegra.INCERTA


def test_corrente_por_mppt(processo):
    processo.visita.area_concessao = "ceara"
    inv, mod = processo.kit.inversor, processo.kit.modulo
    inv.corrente_max_entrada_a, mod.isc_a = 16, 14
    r = avaliar(processo)  # 1 string por MPPT: 14 A ok, 1,25 x 14 = 17,5 A alerta
    assert r.status == StatusRegra.APROVADA and any("1,25" in a for a in r.alertas)
    processo.kit.strings = [
        StringFV(mppt=1, modulos_em_serie=5),
        StringFV(mppt=1, modulos_em_serie=5),
    ]
    r = avaliar(processo)  # 2 em paralelo: 28 A > 16 A
    assert r.status == StatusRegra.REPROVADA and "MPPT 1" in r.mensagem


def test_janela_do_mppt_so_alerta(processo):
    processo.visita.area_concessao = "ceara"
    processo.kit.strings = [StringFV(mppt=1, modulos_em_serie=1)]  # Vmp 42 V < 80 V
    r = avaliar(processo)
    assert r.status == StatusRegra.APROVADA and any("janela" in a for a in r.alertas)


def test_strings_sugeridas_viram_premissa_e_ausentes_ficam_incertas(processo):
    processo.visita.area_concessao = "ceara"
    assert any("sugerida" in p for p in avaliar(processo).premissas)
    processo.kit.strings = []
    assert avaliar(processo).status == StatusRegra.INCERTA
