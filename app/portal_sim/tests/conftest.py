import pytest


@pytest.fixture(autouse=True)
def db_temporario(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.setenv("RELOGIO_INICIO", "2026-11-13")
    monkeypatch.delenv("FERIADOS_UF", raising=False)
    for nome in ("LLM_PRECO_ENTRADA_USD_MTOK", "LLM_PRECO_SAIDA_USD_MTOK", "USD_BRL"):
        monkeypatch.delenv(nome, raising=False)


@pytest.fixture(autouse=True)
def llm_indisponivel(monkeypatch):
    """Por padrão os testes do portal rodam sem LLM (mesmo com chaves no ambiente)."""
    monkeypatch.setattr("app.core.llm.disponivel", lambda papel: False)
