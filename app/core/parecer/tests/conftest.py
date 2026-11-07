from pathlib import Path

import pytest

from app.schemas import CampoExtraido, Fonte, Processo

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures"


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("RELOGIO_INICIO", "2026-11-16")


@pytest.fixture
def processo() -> Processo:
    """Fixture de exemplo: 10 x 550 Wp, inversor 5 kW, 2 strings de 5, padrão 50 A."""
    p = Processo.model_validate_json((FIXTURES / "processo_exemplo.json").read_text())
    return p


def campo(valor, confianca: float = 0.95) -> CampoExtraido:
    return CampoExtraido(valor=valor, confianca=confianca, fonte=Fonte(documento="t"))
