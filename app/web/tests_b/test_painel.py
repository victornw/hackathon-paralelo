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
    r = cliente.get("/processos/proc-demo-006/timeline?detalhes=1")
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
    r = cliente.get("/processos/proc-demo-006/timeline?detalhes=1")
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


def test_painel_foca_o_processo_escolhido(cliente):
    r = cliente.get("/painel?p=proc-demo-006")
    assert r.status_code == 200
    assert 'href="/painel?p=proc-demo-006" aria-current="true"' in r.text
    assert "Processo em foco" in r.text
    assert "Agora:" in r.text


def test_painel_alterna_conversa_do_integrador_e_do_cliente(cliente):
    r = cliente.get("/painel?p=proc-demo-006")
    assert 'id="aba-integrador"' in r.text and 'id="aba-cliente"' in r.text
    assert (
        'id="fio-cliente" role="tabpanel" aria-labelledby="aba-cliente" hidden'
        in r.text
    )
    assert "Olá, Lucia! Pedimos a vistoria à Enel." in r.text


def test_painel_com_id_desconhecido_cai_no_padrao(cliente):
    r = cliente.get("/painel?p=nao-existe")
    assert r.status_code == 200
    assert 'aria-current="true"' in r.text


def test_metricas_mostra_carteira_e_evals(cliente):
    r = cliente.get("/metricas")
    assert r.status_code == 200
    assert "Processos ativos" in r.text
    assert "Regras que mais dispararam" in r.text
    assert "[X]" not in r.text and "[N]" not in r.text


def test_timeline_padrao_mostra_so_marcos():
    from datetime import datetime

    from app.schemas import PassoTrace
    from app.web.painel import _so_marcos

    def ag(nome):
        return {
            "tipo": "agente",
            "titulo": nome,
            "passo": PassoTrace(processo_id="x", passo=nome, em=datetime(2026, 11, 8)),
        }

    itens = [
        ag("decidir_proximo_passo"),
        ag("gerar_documentos"),
        ag("modelo_agente_ai_sdk"),
        ag("gerar_documentos"),
        ag("conferir"),
    ]
    assert [i["titulo"] for i in _so_marcos(itens)] == [
        "Gerou os documentos",
        "Conferiu contra a norma da Enel",
    ]


def test_custo_medido_vem_do_resultado_do_eval():
    from app.web.metricas import eval_processo_completo

    texto = (
        "Médias de 6 execução(ões), 6 concluída(s): 8.0 chamadas LLM, 10033 tokens in, "
        "3017 tokens out, 90.4 s de relógio.\nCusto médio por processo: R$ 0.0719\n"
    )
    r = eval_processo_completo(texto)
    assert r["custo"] == "0,07" and r["chamadas"] == "8" and r["segundos"] == "90,4"
    assert r["tokens"] == "13,1"
