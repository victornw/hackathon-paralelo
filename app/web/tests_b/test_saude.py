from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.web import saude


def _cliente():
    app = FastAPI()
    app.include_router(saude.router)
    return TestClient(app)


def test_sem_ia_aponta_o_que_falta_sem_mostrar_segredo(monkeypatch):
    for v in (
        "FEATHERLESS_API_KEY",
        "MODELO_PRINCIPAL",
        "MODELO_EXTRACAO",
        "MODELO_FALLBACK",
    ):
        monkeypatch.delenv(v, raising=False)
    d = _cliente().get("/saude").json()
    assert d["ok"] is False
    assert "FEATHERLESS_API_KEY não definida" in d["problemas"]
    assert "MODELO_PRINCIPAL não definido" in d["problemas"]
    assert d["ia"]["papeis_disponiveis"]["extracao"] is False


def test_com_ia_mostra_o_modelo_e_nunca_a_chave(monkeypatch):
    monkeypatch.setenv("FEATHERLESS_API_KEY", "segredo-de-teste-123")
    monkeypatch.setenv("MODELO_PRINCIPAL", "Qwen/Qwen3.8-27B")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abcdef1234567")
    r = _cliente().get("/saude")
    assert "segredo-de-teste-123" not in r.text
    d = r.json()
    assert d["ia"]["chave_definida"] is True
    assert d["ia"]["modelo_principal"] == "Qwen/Qwen3.8-27B"
    assert d["ia"]["papeis_disponiveis"]["extracao"] is True
    assert d["commit"] == "abcdef1"


def test_pacotes_ausentes_viram_problema(monkeypatch, tmp_path):
    monkeypatch.setattr(saude, "RAIZ", tmp_path)
    d = _cliente().get("/saude").json()
    assert any("npm ci" in p for p in d["problemas"])
