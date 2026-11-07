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


def test_timeline_mostra_prompt_usado(cliente):
    from app.tracing import carregar_prompt, processo_atual, registrar_uso, trace

    prompt = carregar_prompt("classificar_pendencia")

    @trace("classificar_pendencia")
    def passo():
        registrar_uso(prompt=prompt, decisao="ok")

    with processo_atual("proc-demo-006"):
        passo()
    r = cliente.get("/processos/proc-demo-006/timeline")
    assert f"Prompt: classificar_pendencia v1 ({prompt.hash})" in r.text


def test_faixa_de_prazos_vigiados_ordena_por_urgencia(cliente):
    from datetime import date

    from app.web.painel import carregar_processos, proximos_prazos

    itens = proximos_prazos(carregar_processos(), date(2026, 11, 13))
    situacoes = [i["x"].situacao for i in itens]
    ordem = {"vencido": 0, "vence_hoje": 1, "atencao": 2, "no_prazo": 3}
    assert situacoes == sorted(situacoes, key=ordem.get)
    assert all(i["quem"] in ("Integrador", "Enel") for i in itens)
    integrador = [i for i in itens if i["quem"] == "Integrador"]
    assert integrador and all(i["link"].endswith("/chat") for i in integrador)

    r = cliente.get("/painel")
    assert "Prazos que o agente está vigiando" in r.text
    assert "Venceu em 12/11" in r.text  # vistoria da Lucia: Enel fora do prazo
