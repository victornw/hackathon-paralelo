from pathlib import Path

import pytest

from app.schemas import Processo

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


@pytest.fixture(autouse=True)
def ambiente_temporario(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.setenv("DOCS_DIR", str(tmp_path / "docs"))
    monkeypatch.setenv("RELOGIO_INICIO", "2026-11-09")


@pytest.fixture
def processo() -> Processo:
    return Processo.model_validate_json(
        (FIXTURES / "processo_exemplo.json").read_text()
    )
