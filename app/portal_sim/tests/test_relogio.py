from datetime import date

import pytest

from app.portal_sim import avancar_tempo, definir_data, hoje


def test_comeca_em_relogio_inicio():
    assert hoje() == date(2026, 11, 13)


def test_avancar_persiste():
    assert avancar_tempo(3) == date(2026, 11, 16)
    assert hoje() == date(2026, 11, 16)
    assert avancar_tempo(0) == date(2026, 11, 16)


def test_nao_volta_no_tempo():
    with pytest.raises(ValueError):
        avancar_tempo(-1)


def test_definir_data_para_reset_da_demo():
    avancar_tempo(30)
    definir_data(date(2026, 11, 9))
    assert hoje() == date(2026, 11, 9)
