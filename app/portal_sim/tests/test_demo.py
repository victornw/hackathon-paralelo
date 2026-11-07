from datetime import date

import pytest

from app.core import orquestrador
from app.core import repositorio as repo
from app.portal_sim import portal
from app.portal_sim.demo import CASOS, reiniciar_demo
from app.portal_sim.relogio import avancar_tempo, hoje
from app.schemas import Etapa, Processo, StatusRegra
from app.tracing import listar_passos


@pytest.fixture(autouse=True)
def docs_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCS_DIR", str(tmp_path / "docs"))
    monkeypatch.delenv("DEMO_DATA", raising=False)


def _por_id():
    return {p.id: p for p in repo.listar()}


def test_reiniciar_cria_quatro_casos_coerentes():
    assert reiniciar_demo() == date(2026, 11, 16)
    assert hoje() == date(2026, 11, 16)
    ps = _por_id()
    etapas = {pid: ps[pid].etapa for pid, _, _ in CASOS}
    assert etapas == {
        "demo-01": Etapa.EM_REVISAO,
        "demo-02": Etapa.PENDENCIA,
        "demo-03": Etapa.ORCAMENTO_EMITIDO,
        "demo-04": Etapa.CONCLUIDO,
    }
    for p in ps.values():
        assert p.simulacao
        assert not [r for r in p.regras if r.status == StatusRegra.REPROVADA]
        assert {d.tipo for d in p.documentos} == {
            "solicitacao_orcamento",
            "memorial",
            "unifilar",
        }
        assert listar_passos(p.id)  # tracing real, não inventado
    assert ps["demo-01"].numero_solicitacao is None
    assert ps["demo-02"].eventos[-1].motivo_pendencia
    (prazo,) = ps["demo-03"].prazos
    assert prazo.tipo == "aprovar_orcamento" and prazo.vencimento > hoje()
    assert len(portal.listar_solicitacoes()) == 3


def test_data_da_demo_pelo_env(monkeypatch):
    monkeypatch.setenv("DEMO_DATA", "2026-12-01")
    assert reiniciar_demo() == date(2026, 12, 1)


def test_reiniciar_de_novo_desfaz_o_progresso_e_nao_duplica():
    reiniciar_demo()
    numero = _por_id()["demo-03"].numero_solicitacao
    portal.aprovar_orcamento(numero)
    avancar_tempo(20)
    reiniciar_demo()
    ps = _por_id()
    assert hoje() == date(2026, 11, 16)
    assert ps["demo-03"].etapa == Etapa.ORCAMENTO_EMITIDO
    assert len(portal.listar_solicitacoes()) == 3
    assert len([p for p in ps if p.startswith("demo-")]) == 4
    # números estáveis entre reinícios
    assert ps["demo-03"].numero_solicitacao == numero


def test_processos_de_outras_pessoas_ficam():
    outro = Processo.model_validate(
        {"id": "proc-jurado", "criado_em": "2026-11-16T10:00:00"}
    )
    repo.salvar(outro)
    reiniciar_demo()
    assert "proc-jurado" in _por_id()


def test_orquestrador_roda_nos_casos_sem_falha():
    reiniciar_demo()
    for pid, _, _ in CASOS:
        orquestrador.orquestrar(pid)
    for p in repo.listar():
        assert not [q for q in p.perguntas if q.id.startswith("falha:")], p.id
    assert _por_id()["demo-02"].eventos[-1].categoria_pendencia


def test_garantir_demo_recria_so_quando_falta(monkeypatch):
    from app.portal_sim.demo import garantir_demo

    assert garantir_demo() is True  # banco vazio: recria
    assert {p.id for p in repo.listar()} >= {pid for pid, _, _ in CASOS}
    assert garantir_demo() is False  # já existem: não mexe
    monkeypatch.setenv("DEMO_AUTO", "0")
    assert garantir_demo() is False


def test_site_sobe_com_os_casos_prontos(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as cliente:  # dispara o startup
        ids = {p["id"] for p in cliente.get("/api/processos").json()}
    assert {"demo-01", "demo-02", "demo-03", "demo-04"} <= ids
