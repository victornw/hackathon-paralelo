from pathlib import Path

import pytest

from app.docs.gerar import gerar_documentos
from app.schemas import Processo

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


@pytest.fixture(autouse=True)
def ambiente_temporario(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.setenv("DOCS_DIR", str(tmp_path / "docs"))
    monkeypatch.setenv("RELOGIO_INICIO", "2026-11-09")
    for nome in ("LLM_PRECO_ENTRADA_USD_MTOK", "LLM_PRECO_SAIDA_USD_MTOK", "USD_BRL"):
        monkeypatch.delenv(nome, raising=False)


def _carregar(nome: str) -> Processo:
    return Processo.model_validate_json((FIXTURES / nome).read_text())


@pytest.fixture
def processo() -> Processo:
    return _carregar("processo_exemplo.json")


@pytest.fixture
def protocolado() -> Processo:
    return _carregar("processo_protocolado.json")


@pytest.fixture
def confirmado(processo: Processo) -> Processo:
    """Exemplo com strings confirmadas, cabo informado e disjuntor CA de 25 A."""
    for s in processo.kit.strings:
        s.sugerida = False
    processo.visita.bitola_ca_mm2 = 4
    return processo


@pytest.fixture
def com_documentos(confirmado: Processo) -> Processo:
    confirmado.documentos = gerar_documentos(confirmado)
    return confirmado
