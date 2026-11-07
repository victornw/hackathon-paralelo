from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import repositorio as repo
from app.schemas import Camada, Processo, ResultadoRegra, StatusRegra
from app.web import painel


def _cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("RELOGIO_INICIO", "2026-11-16")
    app = FastAPI()
    app.include_router(painel.router)
    return TestClient(app)


def _processo(confirmavel: bool) -> Processo:
    return Processo(
        id="p-r05",
        criado_em=datetime(2026, 11, 16, 9),
        regras=[
            ResultadoRegra(
                regra_id="R05",
                descricao="INMETRO",
                camada=Camada.DISTRIBUIDORA,
                status=StatusRegra.INCERTA,
                valores={"confirmavel": "sim"} if confirmavel else {},
                mensagem="Registro ativo sem tensão; datasheet 220 V.",
                fonte_norma="Portaria 140",
            )
        ],
    )


def test_engenheiro_confirma_r05(tmp_path, monkeypatch):
    c = _cliente(tmp_path, monkeypatch)
    repo.salvar(_processo(True))
    r = c.post("/processos/p-r05/regras/R05/confirmar", data={"engenheiro": "Eng. Ana"})
    assert r.status_code == 200 and r.json()["confirmado_por"] == "Eng. Ana"
    assert repo.carregar("p-r05").regras[0].confirmado_por == "Eng. Ana"


def test_r05_nao_confirmavel_recusa(tmp_path, monkeypatch):
    c = _cliente(tmp_path, monkeypatch)
    repo.salvar(_processo(False))
    r = c.post("/processos/p-r05/regras/R05/confirmar", data={"engenheiro": "Eng. Ana"})
    assert r.status_code == 409


def test_processo_inexistente(tmp_path, monkeypatch):
    c = _cliente(tmp_path, monkeypatch)
    r = c.post("/processos/nao/regras/R05/confirmar", data={"engenheiro": "Eng. Ana"})
    assert r.status_code == 404
