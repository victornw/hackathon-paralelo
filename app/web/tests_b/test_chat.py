import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.schemas import Etapa
from app.web import painel


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("RELOGIO_INICIO", "2026-11-13")
    app = FastAPI()
    app.include_router(painel.router)
    return TestClient(app)


def test_chat_mostra_duas_colunas(cliente):
    r = cliente.get("/processos/proc-demo-006/chat")
    assert r.status_code == 200
    assert "Integrador" in r.text
    assert "Cliente final (WhatsApp simulado)" in r.text
    assert "Simulação" in r.text
    assert "Pela norma, a Enel tem até 12/11/2026" in r.text


def test_chat_inexistente(cliente):
    assert cliente.get("/processos/nao-existe/chat").status_code == 404


def test_chat_form_por_pergunta_e_url_da_api(cliente):
    r = cliente.get("/processos/proc-demo-003/chat")
    assert r.status_code == 200
    assert "/api/processos/proc-demo-003/respostas" in r.text
    assert r.text.count('class="resposta"') == 2  # só as do integrador
    assert "Enviar resposta" in r.text
    assert 'role="alert"' in r.text


def test_chat_vazio_mostra_aviso(cliente, monkeypatch):
    vazio = painel.carregar_processos()[0].model_copy(
        update={"perguntas": [], "eventos": [], "etapa": Etapa.MONTAGEM}
    )
    monkeypatch.setattr(painel, "carregar_processos", lambda: [vazio])
    r = cliente.get(f"/processos/{vazio.id}/chat")
    assert r.text.count("Nenhuma mensagem ainda.") == 2


def test_links_para_o_chat(cliente):
    # A conversa do processo em foco fica na coluna da direita do painel.
    assert (
        "/processos/proc-demo-006/chat"
        in cliente.get("/painel?p=proc-demo-006").text
    )
    assert (
        "/processos/proc-demo-006/chat"
        in cliente.get("/processos/proc-demo-006/timeline").text
    )
