import pytest


@pytest.fixture(autouse=True)
def db_temporario(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.setenv("RELOGIO_INICIO", "2026-11-13")
    monkeypatch.delenv("FERIADOS_UF", raising=False)
    for nome in ("LLM_PRECO_ENTRADA_USD_MTOK", "LLM_PRECO_SAIDA_USD_MTOK", "USD_BRL"):
        monkeypatch.delenv(nome, raising=False)
