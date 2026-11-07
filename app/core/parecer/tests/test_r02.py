import pytest

from app.core.parecer.r02_cabo import avaliar, iz_corrigido, queda_tensao_pct
from app.schemas import StatusRegra


@pytest.fixture
def p(processo):
    """Fixture: Ib 22,7 A, disjuntor 25 A, 8 m. Falta só a seção: usar 6 mm²."""
    processo.visita.bitola_ca_mm2 = 6
    return processo


def test_iz_corrigido_confere_com_o_parecer():
    # B2, 35 °C, 2 circuitos: 22,6 A (4 mm²), 28,6 A (6 mm²), 39,1 A (10 mm²)
    assert iz_corrigido(4, "B2", "interno", 2)[3] == 22.6
    assert iz_corrigido(6, "B2", "interno", 2)[3] == 28.6
    assert iz_corrigido(10, "B2", "interno", 2)[3] == 39.1
    # Tabela 36 sem correção: 2,5 mm² A1 19,5 A, A2 18,5 A, B2 23 A
    assert iz_corrigido(2.5, "A1", "interno", 1)[0] == 19.5
    assert iz_corrigido(2.5, "A2", "interno", 1)[0] == 18.5
    assert iz_corrigido(2.5, "B2", "interno", 1)[0] == 23


def test_queda_de_tensao_do_parecer():
    assert round(queda_tensao_pct(22.7, 15, 6, 220), 2) == 1.10
    assert queda_tensao_pct(22.7, 27, 6, 220) < 2 < queda_tensao_pct(22.7, 28, 6, 220)
    assert queda_tensao_pct(22.7, 54, 6, 220) < 4 < queda_tensao_pct(22.7, 55, 6, 220)


def test_caso_padrao_aprova_com_premissas_declaradas(p):
    r = avaliar(p)
    assert r.status == StatusRegra.APROVADA
    assert r.valores["iz_corrigido_a"] == 28.6
    assert len(r.premissas) == 4  # método, isolação, ambiente, agrupamento
    assert "premissa assumida" in r.mensagem and "B2" in r.mensagem


def test_sem_premissas_quando_tudo_informado(p):
    v = p.visita
    v.metodo_instalacao, v.isolacao, v.ambiente_cabo, v.circuitos_agrupados = (
        "B2",
        "PVC",
        "interno",
        2,
    )
    r = avaliar(p)
    assert r.status == StatusRegra.APROVADA and r.premissas == []
    assert "premissa" not in r.mensagem


def test_disjuntor_acima_do_iz_corrigido_reprova(p):
    p.visita.disjuntor_ca_a = 32  # 32 A > 28,6 A em 6 mm²
    r = avaliar(p)
    assert r.status == StatusRegra.REPROVADA and "capacidade corrigida" in r.mensagem
    p.visita.bitola_ca_mm2 = 10  # 39,1 A
    assert avaliar(p).status == StatusRegra.APROVADA


def test_ib_acima_do_disjuntor_reprova(p):
    p.visita.disjuntor_ca_a = 20
    assert avaliar(p).status == StatusRegra.REPROVADA


def test_fator_1_25_so_quando_o_manual_indica(p):
    assert avaliar(p).status == StatusRegra.APROVADA  # 25 A sem fator no cadastro
    p.kit.inversor.fator_min_disjuntor = 1.25  # 1,25 x 22,7 = 28,4 A
    r = avaliar(p)
    assert r.status == StatusRegra.REPROVADA and "1,25" in r.mensagem
    p.visita.disjuntor_ca_a, p.visita.bitola_ca_mm2 = 32, 10
    assert avaliar(p).status == StatusRegra.APROVADA


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("disjuntor_max_a", 20),
        ("cabo_min_mm2", 10),
        ("terminal_ca_min_mm2", 10),
        ("terminal_ca_max_mm2", 4),
    ],
)
def test_restricoes_do_manual_reprovam(p, campo, valor):
    setattr(p.kit.inversor, campo, valor)
    assert avaliar(p).status == StatusRegra.REPROVADA


def test_cabo_exposto_usa_50_graus(p):
    p.visita.ambiente_cabo = "exposto"  # 38 x 0,71 x 0,80 = 21,6 A < 25 A
    r = avaliar(p)
    assert r.status == StatusRegra.REPROVADA and r.valores["fator_temperatura"] == 0.71


def test_piso_de_2_5_e_iz_domina(p):
    p.visita.bitola_ca_mm2 = 2.5
    assert avaliar(p).status == StatusRegra.REPROVADA  # Iz 17,3 A
    p.visita.bitola_ca_mm2 = 1.5
    assert "piso" in avaliar(p).mensagem


def test_queda_acima_de_2_alerta_e_acima_de_4_reprova(p):
    p.visita.distancia_inversor_quadro_m = 30
    r = avaliar(p)
    assert r.status == StatusRegra.APROVADA and any("2%" in a for a in r.alertas)
    p.visita.distancia_inversor_quadro_m = 60
    assert avaliar(p).status == StatusRegra.REPROVADA


@pytest.mark.parametrize(
    "faltando", ["bitola_ca_mm2", "disjuntor_ca_a", "distancia_inversor_quadro_m"]
)
def test_dado_obrigatorio_ausente_fica_incerto(p, faltando):
    setattr(p.visita, faltando, None)
    r = avaliar(p)
    assert r.status == StatusRegra.INCERTA and "Não verificável" in r.mensagem


def test_xlpe_ainda_nao_validado_fica_incerto(p):
    p.visita.isolacao = "XLPE"
    assert avaliar(p).status == StatusRegra.INCERTA


def test_icc_informado_vira_alerta_nao_reprova(p):
    p.visita.icc_ka = 5
    r = avaliar(p)
    assert r.status == StatusRegra.APROVADA and any("Icc" in a for a in r.alertas)
