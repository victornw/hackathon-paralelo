import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.schemas import DocumentoGerado, Processo
from app.web import painel

RAIZ = Path(__file__).resolve().parents[3]
QUANDO = datetime(2026, 11, 5, 14, 30)


def _doc(tipo, nome, formato):
    return DocumentoGerado(
        tipo=tipo,
        nome_arquivo=nome,
        caminho=f"/tmp/{nome}",
        formato=formato,
        gerado_em=QUANDO,
    )


QUATRO = [
    ("solicitacao_orcamento", "anexo_a.pdf", "pdf"),
    ("memorial", "memorial.pdf", "pdf"),
    ("unifilar", "unifilar.pdf", "pdf"),
    ("unifilar", "unifilar.svg", "svg"),
]


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    caminho = tmp_path / "t.db"
    monkeypatch.setenv("DB_PATH", str(caminho))
    monkeypatch.setenv("RELOGIO_INICIO", "2026-11-13")
    return caminho


@pytest.fixture
def cliente(db_path):
    app = FastAPI()
    app.include_router(painel.router)
    return TestClient(app)


def _inserir(db_path, docs):
    base = json.loads((RAIZ / "fixtures" / "processo_exemplo.json").read_text())
    p = Processo.model_validate(base)
    p.documentos = [_doc(*d) for d in docs]
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE IF NOT EXISTS processos(id TEXT PRIMARY KEY, json TEXT)")
    con.execute(
        "INSERT OR REPLACE INTO processos(id, json) VALUES (?, ?)",
        (p.id, p.model_dump_json()),
    )
    con.commit()
    con.close()
    return p.id


def test_rota_devolve_fragmento_com_tres_linhas_e_links(cliente, db_path):
    pid = _inserir(db_path, QUATRO)
    r = cliente.get(f"/processos/{pid}/documentos")
    assert r.status_code == 200
    assert "<html" not in r.text
    assert "Documentos gerados" in r.text
    assert r.text.count("<li>") == 3
    for rotulo in (
        "Solicitação de orçamento (Anexo A)",
        "Memorial descritivo",
        "Diagrama unifilar",
    ):
        assert rotulo in r.text
    base = f"/processos/{pid}/documentos/"
    for nome in ("anexo_a.pdf", "memorial.pdf", "unifilar.pdf", "unifilar.svg"):
        assert f'href="{base}{nome}/ver"' in r.text
    assert "05/11/2026 14:30" in r.text
    assert 'target="_blank" rel="noopener"' in r.text
    assert "Ainda não gerado" not in r.text
    assert "Revise cada documento antes de aprovar e assinar." in r.text


def test_sem_documentos_mostra_estado_vazio(cliente, db_path):
    pid = _inserir(db_path, [])
    r = cliente.get(f"/processos/{pid}/documentos")
    assert r.status_code == 200
    assert "Os documentos aparecem aqui quando o agente gerar o projeto." in r.text
    assert "<li>" not in r.text


def test_tipo_ausente_mostra_ainda_nao_gerado(cliente, db_path):
    pid = _inserir(db_path, QUATRO[:2])
    r = cliente.get(f"/processos/{pid}/documentos")
    assert r.text.count("Ainda não gerado") == 1
    assert r.text.count("<li>") == 3


def test_processo_inexistente_404(cliente):
    assert cliente.get("/processos/nao-existe/documentos").status_code == 404


def test_timeline_inclui_bloco(cliente):
    r = cliente.get("/processos/proc-demo-006/timeline")
    assert r.status_code == 200
    assert "Documentos gerados" in r.text


def test_nome_com_espaco_e_codificado(cliente, db_path):
    pid = _inserir(db_path, [("memorial", "memorial final.pdf", "pdf")])
    r = cliente.get(f"/processos/{pid}/documentos")
    assert f"/processos/{pid}/documentos/memorial%20final.pdf/ver" in r.text
    assert "memorial final.pdf" not in r.text


def test_contexto_documentos(db_path):
    pid = _inserir(db_path, QUATRO)
    p = next(x for x in painel.carregar_processos() if x.id == pid)
    ctx = painel.contexto_documentos(p)
    assert ctx["processo_id"] == pid
    assert len(ctx["documentos"]) == 4
