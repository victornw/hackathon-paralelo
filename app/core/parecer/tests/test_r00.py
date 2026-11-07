import pytest

from app.core.parecer.r00_potencia import avaliar
from app.core.parecer.tests.conftest import campo
from app.schemas import StatusRegra


@pytest.mark.parametrize(
    ("disjuntor", "potencia_w", "status"),
    [
        (40, 10_000, StatusRegra.REPROVADA),  # exemplo do parecer: 10 kW em 40 A
        (40, 8_800, StatusRegra.APROVADA),  # exatamente no limite
        (40, 8_801, StatusRegra.REPROVADA),
        (20, 4_400, StatusRegra.APROVADA),
        (25, 5_000, StatusRegra.APROVADA),
        (32, 7_040, StatusRegra.APROVADA),
        (50, 11_000, StatusRegra.APROVADA),
        (63, 13_860, StatusRegra.APROVADA),
        (63, 15_000, StatusRegra.REPROVADA),
    ],
)
def test_tabela_monofasica(processo, disjuntor, potencia_w, status):
    processo.visita.disjuntor_padrao_a = campo(disjuntor)
    processo.kit.inversor.potencia_nominal_w = potencia_w
    r = avaliar(processo)
    assert r.status == status
    assert r.regra_id == "R00"
    assert "7.2.4" in r.fonte_norma


def test_mensagem_do_exemplo_do_parecer(processo):
    processo.visita.disjuntor_padrao_a = campo(40)
    processo.kit.inversor.potencia_nominal_w = 10_000
    r = avaliar(processo)
    assert "10,00 kW" in r.mensagem and "8,80 kW" in r.mensagem
    assert r.valores["potencia_disponibilizada_kw"] == 8.80


def test_vigencia_da_tabela_vira_premissa_declarada(processo):
    r = avaliar(processo)  # fixture: 5 kW, padrão 50 A
    assert r.status == StatusRegra.APROVADA
    assert any("vigente" in p for p in r.premissas)
    assert "premissa assumida" in r.mensagem


def test_sem_disjuntor_nao_verificavel(processo):
    processo.visita.disjuntor_padrao_a = None
    r = avaliar(processo)
    assert r.status == StatusRegra.INCERTA
    assert "Não verificável" in r.mensagem


def test_disjuntor_ilegivel_fica_incerto(processo):
    processo.visita.disjuntor_padrao_a = campo(40, confianca=0.5)
    assert avaliar(processo).status == StatusRegra.INCERTA


def test_disjuntor_fora_da_tabela_usa_220_vezes_in_com_alerta(processo):
    processo.visita.disjuntor_padrao_a = campo(35)
    processo.kit.inversor.potencia_nominal_w = 7_000
    r = avaliar(processo)
    assert r.status == StatusRegra.APROVADA  # 220 x 35 = 7,70 kW
    assert r.valores["potencia_disponibilizada_kw"] == 7.7
    assert r.alertas and "fora da tabela" in r.alertas[0]


def test_trifasico_fica_fora_da_tabela(processo):
    processo.campos["tipo_ligacao"] = campo("trifasico")
    assert avaliar(processo).status == StatusRegra.NAO_VERIFICADA


def test_sem_kit(processo):
    processo.kit = None
    assert avaliar(processo).status == StatusRegra.INCERTA
