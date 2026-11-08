import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import orquestrador, repositorio
from app.schemas import Etapa, Pergunta, Processo
from app.web import processo

RAIZ = Path(__file__).resolve().parents[3]


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("DOCS_DIR", str(tmp_path / "docs"))
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("RELOGIO_INICIO", "2026-11-16")
    monkeypatch.setattr("app.core.llm.disponivel", lambda: False)
    monkeypatch.setattr(orquestrador, "orquestrar", lambda pid: None)
    app = FastAPI()
    app.include_router(processo.router)
    return TestClient(app)


def _exemplo(**mudancas) -> Processo:
    dados = json.loads((RAIZ / "fixtures" / "processo_exemplo.json").read_text())
    p = Processo.model_validate(dados)
    return p.model_copy(update=mudancas) if mudancas else p


def test_novo_mostra_formulario_e_exemplos(cliente):
    r = cliente.get("/processos/novo")
    assert r.status_code == 200
    for trecho in (
        'name="email"',
        'name="conta"',
        'name="proposta"',
        'name="datasheet"',
        'name="padrao"',
    ):
        assert trecho in r.text
    for n in (1, 2, 3):
        assert f"Usar exemplo {n}" in r.text
        assert f'action="/processos/novo/exemplo/{n}"' in r.text
    assert 'role="alert"' in r.text


def test_exemplo_cria_processo_com_dois_arquivos(cliente):
    r = cliente.post("/processos/novo/exemplo/1", follow_redirects=False)
    assert r.status_code == 303
    pid = r.headers["location"].removeprefix("/processos/")
    assert repositorio.carregar(pid).id == pid
    arqs = repositorio.arquivos(pid)
    assert len(arqs["conta"]) == 1 and len(arqs["proposta"]) == 1
    assert cliente.get(r.headers["location"]).status_code == 200


def test_exemplo_invalido_404(cliente):
    assert cliente.post("/processos/novo/exemplo/4").status_code == 404
    assert cliente.post("/processos/novo/exemplo/0").status_code == 404


def test_detalhe_do_processo_exemplo(cliente):
    p = _exemplo()
    repositorio.salvar(p)
    r = cliente.get(f"/processos/{p.id}")
    assert r.status_code == 200
    titular = str(p.campos["titular"].valor).title()
    assert titular in r.text
    assert "Dados da conta de luz" in r.text and "Código da UC" in r.text
    assert "%" in r.text
    assert "Kit vendido" in r.text and "módulos em série" in r.text
    assert "Responder" in r.text and "O que falta" in r.text
    assert "Conferência" in r.text and "R01" in r.text
    assert "Documentos gerados" in r.text
    assert f"/processos/{p.id}/timeline" in r.text
    assert f"/processos/{p.id}/chat" in r.text


def test_detalhe_inexistente_404(cliente):
    r = cliente.get("/processos/nao-existe")
    assert r.status_code == 404
    assert "não encontrado" in r.text


def test_montagem_sem_campos_mostra_trabalhando(cliente):
    p = repositorio.criar(email_contato="a@exemplo.com")
    r = cliente.get(f"/processos/{p.id}")
    assert r.status_code == 200
    assert "O agente está trabalhando" in r.text
    assert 'http-equiv="refresh"' in r.text or "location.reload" in r.text
    assert "Processo novo" in r.text
    assert "O kit aparece aqui quando o agente ler a proposta." in r.text


def test_falha_mostra_tentar_de_novo(cliente):
    p = _exemplo(
        etapa=Etapa.MONTAGEM,
        perguntas=[
            Pergunta(
                id="falha:extrair", campo="extrair", texto="Não consegui ler a conta."
            )
        ],
    )
    repositorio.salvar(p)
    r = cliente.get(f"/processos/{p.id}")
    assert "Tentar de novo" in r.text
    assert "Não consegui ler a conta." in r.text
    assert "O agente está trabalhando" not in r.text
    assert "rodar?refazer=true" in r.text


def test_em_revisao_mostra_link_revisar(cliente):
    p = _exemplo()
    assert p.etapa == Etapa.EM_REVISAO
    repositorio.salvar(p)
    r = cliente.get(f"/processos/{p.id}")
    assert "Revisar e assinar" in r.text
    assert f"/processos/{p.id}/revisao" in r.text
    p2 = _exemplo(id="outro", etapa=Etapa.PROTOCOLADO)
    repositorio.salvar(p2)
    assert "Revisar e assinar" not in cliente.get("/processos/outro").text
