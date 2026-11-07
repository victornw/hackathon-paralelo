import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.web import painel


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("RELOGIO_INICIO", "2026-11-13")
    app = FastAPI()
    app.include_router(painel.router)
    return TestClient(app)


def test_painel_mostra_carteira_por_etapa_e_selo(cliente):
    r = cliente.get("/painel")
    assert r.status_code == 200
    assert "7 processos" in r.text
    assert "Simulação" in r.text
    assert "Aprovar o orçamento" in r.text


def test_timeline_com_prazo_e_eventos(cliente):
    r = cliente.get("/processos/proc-demo-006/timeline")
    assert r.status_code == 200
    assert "Vence em 12/11/2026" in r.text  # 05/11 + 5 dias úteis
    assert "Sem execuções medidas ainda" in r.text


def test_timeline_inexistente(cliente):
    assert cliente.get("/processos/nao-existe/timeline").status_code == 404
