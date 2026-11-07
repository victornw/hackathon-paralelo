import re
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.portal_sim import portal
from app.schemas import Carga, Etapa, Pergunta, Processo
from app.web import painel

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
BANNER = "Portal simulado para demonstração. Não é o portal da Enel; dados sintéticos."


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("RELOGIO_INICIO", "2026-11-13")
    monkeypatch.setattr("app.core.llm.disponivel", lambda papel: False)


@pytest.fixture
def cliente():
    app = FastAPI()
    app.include_router(painel.router)  # só o router do painel
    return TestClient(app)


@pytest.fixture
def pronto() -> Processo:
    p = Processo.model_validate_json((FIXTURES / "processo_exemplo.json").read_text())
    p.visita.relacao_cargas = [Carga(descricao="Geladeira", potencia_w=250)]
    p.perguntas += [
        Pergunta(id="t", campo="telefone", texto="?", resposta="(00) 90000-0000"),
        Pergunta(
            id="m",
            campo="modalidade_compensacao",
            texto="?",
            resposta="Autoconsumo local",
        ),
        Pergunta(id="u", campo="qtd_ucs_credito", texto="?", resposta="1"),
    ]
    p.revisado_por = "Eng. Exemplo"
    p.revisado_em = datetime(2026, 11, 13, 10)
    return p


@pytest.fixture
def sol(pronto):
    numero = portal.protocolar(pronto)
    form = portal.formulario(numero)
    return {"numero": numero, "uc": form.codigo_uc, "email": form.email}


def consulta(cliente, sol, **alt):
    return cliente.get("/portal-gd/consulta", params={**sol, **alt})


def acao(cliente, sol, nome, **extra):
    return cliente.post(
        f"/portal-gd/acoes/{nome}", data={**sol, **extra}, follow_redirects=False
    )


def operador_avanca(cliente, sol):
    return cliente.post(
        f"/portal-gd/operador/{sol['numero']}/avancar", follow_redirects=False
    )


# --- unidade -----------------------------------------------------------------


def test_listar_solicitacoes_e_formulario(pronto):
    assert portal.listar_solicitacoes() == []
    n1 = portal.protocolar(pronto)
    portal.avancar_distribuidora(n1)
    r = portal.listar_solicitacoes()
    assert len(r) == 1
    assert r[0].numero == n1
    assert r[0].etapa == Etapa.PENDENCIA
    assert r[0].titular
    f = portal.formulario(n1)
    assert f.codigo_uc == r[0].uc
    with pytest.raises(portal.SolicitacaoNaoEncontrada):
        portal.formulario("GD-0000-000000")


def test_listar_mais_recente_primeiro(pronto):
    from app.portal_sim import avancar_tempo

    n1 = portal.protocolar(pronto)
    avancar_tempo(1)
    n2 = portal.protocolar(pronto)
    assert [r.numero for r in portal.listar_solicitacoes()] == [n2, n1]


# --- telas -------------------------------------------------------------------


def test_home_com_banner_e_passos(cliente):
    r = cliente.get("/portal-gd")
    assert r.status_code == 200
    assert BANNER in r.text
    assert "Portal de geração distribuída (simulado)" in r.text
    assert "Formulário básico" in r.text and "Confirmação" in r.text
    assert 'for="uc"' in r.text


def test_consulta_correta(cliente, sol):
    r = consulta(cliente, sol)
    assert r.status_code == 200
    assert sol["numero"] in r.text
    assert "Protocolado" in r.text
    assert "Formulário básico" in r.text
    assert "7000123456" in r.text
    assert "13/11/2026" in r.text
    assert "Autoconsumo local" in r.text
    assert BANNER in r.text


def test_consulta_email_errado(cliente, sol):
    r = consulta(cliente, sol, email="outro@exemplo.com")
    assert r.status_code == 200
    assert "Solicitação não encontrada. Confira" in r.text
    assert sol["numero"] not in r.text.split("<form")[0]


def test_consulta_campos_vazios(cliente):
    r = cliente.get(
        "/portal-gd/consulta", params={"uc": "1", "email": "", "numero": ""}
    )
    assert r.status_code == 200
    assert "Solicitação não encontrada" in r.text


def test_nada_de_marca_nem_estado(cliente, sol):
    portal.avancar_distribuidora(sol["numero"])
    paginas = ["/portal-gd", "/portal-gd/operador"]
    textos = [cliente.get(p).text for p in paginas] + [consulta(cliente, sol).text]
    for t in textos:
        sem_banner = t.replace(BANNER, "")
        assert "Enel CE" not in t
        assert "Ceará" not in t
        assert "Enel" not in sem_banner.replace("portal da Enel simulado", "")


def test_caminho_completo(cliente, sol):
    n = sol["numero"]
    # distribuidora aponta pendência
    assert operador_avanca(cliente, sol).status_code == 303
    r = consulta(cliente, sol)
    assert "Pendência" in r.text
    assert "dispositivo de proteção contra surtos" in r.text
    assert "<blockquote>" in r.text
    assert "Reenviar com a correção" in r.text

    # correção vazia
    r = acao(cliente, sol, "reenviar", correcao="  ")
    assert r.status_code == 200
    assert "Descreva a correção" in r.text
    assert portal.listar_solicitacoes()[0].etapa == Etapa.PENDENCIA

    # correção com texto
    r = acao(cliente, sol, "reenviar", correcao="DPS incluído no unifilar")
    assert r.status_code == 303
    assert r.headers["location"].startswith("/portal-gd/consulta?")
    r = cliente.get(r.headers["location"])
    assert "DPS incluído no unifilar" in r.text
    assert portal.listar_solicitacoes()[0].etapa == Etapa.PROTOCOLADO

    operador_avanca(cliente, sol)
    r = consulta(cliente, sol)
    assert "Orçamento emitido" in r.text and "Aprovar orçamento" in r.text

    assert acao(cliente, sol, "aprovar-orcamento").status_code == 303
    r = consulta(cliente, sol)
    assert "Orçamento aprovado" in r.text and "Solicitar vistoria" in r.text

    assert acao(cliente, sol, "solicitar-vistoria").status_code == 303
    r = consulta(cliente, sol)
    assert "Vistoria solicitada" in r.text
    assert portal.listar_solicitacoes()[0].numero == n
    assert portal.listar_solicitacoes()[0].etapa == Etapa.VISTORIA_SOLICITADA


def test_acao_fora_de_etapa_mostra_erro(cliente, sol):
    r = acao(cliente, sol, "aprovar-orcamento")
    assert r.status_code == 200
    assert "Ação indisponível" in r.text


def test_acao_com_uc_errada_da_404(cliente, sol):
    r = acao(cliente, {**sol, "uc": "999"}, "aprovar-orcamento")
    assert r.status_code == 404
    assert "Solicitação não encontrada" in r.text


def test_operador_aguardando_integrador(cliente, sol):
    operador_avanca(cliente, sol)  # -> pendência: agora é a vez do integrador
    r = operador_avanca(cliente, sol)
    assert r.status_code == 303
    pagina = cliente.get(r.headers["location"])
    assert pagina.status_code == 200
    assert "Aguardando o integrador" in pagina.text


def test_operador_vazio(cliente):
    r = cliente.get("/portal-gd/operador")
    assert r.status_code == 200
    assert "Nenhuma solicitação protocolada ainda." in r.text
    assert "+1 dia" in r.text and "+5 dias" in r.text and "+10 dias" in r.text
    assert "Operador do portal" in r.text


def test_operador_lista_solicitacao(cliente, sol):
    r = cliente.get("/portal-gd/operador")
    assert sol["numero"] in r.text
    assert "Próximo passo da distribuidora" in r.text
    assert re.search(r'href="/portal-gd/consulta\?uc=', r.text)


def test_nav_do_painel_liga_ao_portal(cliente):
    r = cliente.get("/painel")
    assert 'href="/portal-gd"' in r.text
    assert 'href="/portal-gd/operador"' in r.text


def test_regua_depois_do_reenvio_mostra_em_analise():
    from datetime import date

    from app.portal_sim.rotas import _passos
    from app.schemas import Etapa, EventoPortal

    def ev(etapa):
        return EventoPortal(
            numero_solicitacao="GD-1",
            etapa=etapa,
            descricao="",
            data=date(2026, 11, 13),
        )

    passos = _passos(
        [ev(Etapa.PROTOCOLADO), ev(Etapa.PENDENCIA), ev(Etapa.PROTOCOLADO)]
    )
    estados = [(p["rotulo"], p["estado"]) for p in passos[:4]]
    assert estados == [
        ("Protocolado", "feito"),
        ("Pendência", "feito"),
        ("Reenviado, em análise", "atual"),
        ("Orçamento emitido", "futuro"),
    ]


def test_botao_reiniciar_demonstracao(cliente, tmp_path, monkeypatch):
    monkeypatch.setenv("DOCS_DIR", str(tmp_path / "docs"))
    pagina = cliente.get("/portal-gd/operador")
    assert "Reiniciar demonstração" in pagina.text
    r = cliente.post("/portal-gd/operador/reiniciar", follow_redirects=False)
    assert r.status_code == 303
    depois = cliente.get(r.headers["location"])
    assert "Demonstração reiniciada" in depois.text
    assert depois.text.count("Próximo passo da distribuidora") == 3
