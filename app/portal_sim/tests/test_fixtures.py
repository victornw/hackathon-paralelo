from pathlib import Path

import pytest

from app.schemas import Processo

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


@pytest.mark.parametrize("nome", ["processo_exemplo.json", "processo_protocolado.json"])
def test_fixture_valida_e_marcada_como_simulacao(nome):
    p = Processo.model_validate_json((FIXTURES / nome).read_text())
    assert p.simulacao is True
