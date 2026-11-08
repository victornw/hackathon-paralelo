import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import repositorio as repo
from app.portal_sim.demo import reiniciar_demo
from app.schemas import Processo
from app.web import painel, revisao

RAIZ = Path(__file__).resolve().parents[3]


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("DOCS_DIR", str(tmp_path / "docs"))
    monkeypatch.setenv("RELOGIO_INICIO", "2026-11-16")
    app = FastAPI()
    app.include_router(revisao.router)
    app.include_router(painel.router)
    return TestClient(app)


def test_pagina_demo_01(cliente):
    reiniciar_demo()
    r = cliente.get("/processos/demo-01/revisao")
    assert r.status_code == 200
    html = r.text
    ids = re.findall(r'id="regra-(R\d\d)"', html)
    assert ids == sorted(ids) and "R00" in ids and "R08" in ids
    assert "Resumo da conferência" in html
    assert "Nada bloqueia a aprovação" not in html
    assert 'class="rev-bloqueios"' in html
    assert re.search(r'<button type="submit"[^>]* disabled>Aprovar e assinar', html)
    assert "demo:strings" in html and "configuração sugerida" in html
    assert "Documentos gerados" in html
    assert "Premissas assumidas" in html or "Alertas" in html


def test_confirmar_r05_presente(cliente):
    reiniciar_demo()
    p = repo.carregar("demo-01")
    r05 = next(x for x in p.regras if x.regra_id == "R05")
    assert r05.valores.get("confirmavel") == "sim"
    html = cliente.get("/processos/demo-01/revisao").text
    assert "Confirmar R05" in html and "confirmar-r05" in html


def test_somente_leitura_concluido(cliente):
    reiniciar_demo()
    r = cliente.get("/processos/demo-04/revisao")
    assert r.status_code == 200
    assert "não está aguardando revisão" in r.text
    assert "Aprovar e assinar" not in r.text
    assert 'id="form-aprovar"' not in r.text


def test_processo_exemplo(cliente):
    p = Processo.model_validate_json(
        (RAIZ / "fixtures" / "processo_exemplo.json").read_text()
    )
    repo.salvar(p)
    assert cliente.get(f"/processos/{p.id}/revisao").status_code == 200


def test_inexistente(cliente):
    assert cliente.get("/processos/nao/revisao").status_code == 404


def test_tempo(cliente):
    reiniciar_demo()
    url = "/processos/demo-01/revisao/tempo"
    r = cliente.post(url, json={"segundos": 600, "resultado": "aprovado"})
    assert r.status_code == 204
    passos = [
        p for p in revisao.listar_passos("demo-01") if p.passo == "revisao_engenheiro"
    ]
    assert passos[-1].ms == 600000
    assert "10 min (aprovado)" in passos[-1].decisao
    assert revisao.minutos_de_revisao("demo-01") == [10.0]
    assert (
        cliente.post(url, json={"segundos": 0, "resultado": "aprovado"}).status_code
        == 422
    )
    assert (
        cliente.post(url, json={"segundos": 20000, "resultado": "aprovado"}).status_code
        == 422
    )
    assert (
        cliente.post(
            "/processos/nao/revisao/tempo",
            json={"segundos": 5, "resultado": "devolvido"},
        ).status_code
        == 404
    )
