from datetime import date, datetime

import pytest

from app.portal_sim.relogio import avancar_tempo
from app.schemas import Processo
from app.tracing import (
    listar_passos,
    processo_atual,
    registrar_uso,
    resumo_custo,
    trace,
)


def _processo(pid: str = "p1") -> Processo:
    return Processo(id=pid, criado_em=datetime(2026, 11, 13, 9, 0))


def test_grava_passo_com_tokens_e_decisao_pelo_contexto():
    @trace("extrair_conta")
    def extrair():
        registrar_uso(1000, 200, decisao="Conta lida.")
        registrar_uso(500, 100)  # segunda chamada de LLM no mesmo passo soma
        return "ok"

    with processo_atual("p1"):
        assert extrair() == "ok"

    (passo,) = listar_passos("p1")
    assert passo.passo == "extrair_conta"
    assert passo.tokens_entrada == 1500
    assert passo.tokens_saida == 300
    assert passo.decisao == "Conta lida."
    assert passo.erro is None
    assert passo.custo_brl == 0.0  # sem preço no .env, custo zero, nunca inventado


def test_processo_id_vem_do_argumento_processo():
    @trace("conferir")
    def conferir(processo):
        return []

    conferir(_processo("p2"))
    assert [p.passo for p in listar_passos("p2")] == ["conferir"]


def test_processo_id_explicito_tem_prioridade():
    @trace("protocolar")
    def protocolar(processo_id=None):
        return "S-1"

    with processo_atual("outro"):
        protocolar(processo_id="p3")
    assert len(listar_passos("p3")) == 1
    assert listar_passos("outro") == []


def test_erro_e_registrado_e_relancado():
    @trace("falha")
    def falha():
        raise ValueError("ilegível")

    with processo_atual("p4"), pytest.raises(ValueError):
        falha()
    (passo,) = listar_passos("p4")
    assert passo.erro == "ValueError: ilegível"


def test_custo_pelos_precos_do_env(monkeypatch):
    monkeypatch.setenv("LLM_PRECO_ENTRADA_USD_MTOK", "3")
    monkeypatch.setenv("LLM_PRECO_SAIDA_USD_MTOK", "15")
    monkeypatch.setenv("USD_BRL", "5")

    @trace("redigir")
    def redigir():
        registrar_uso(1_000_000, 100_000)

    with processo_atual("p5"):
        redigir()
    # (1 * 3 + 0,1 * 15) USD * 5 = 22,5 BRL
    assert resumo_custo("p5").custo_brl == pytest.approx(22.5)


def test_custo_explicito_sobrepoe_tabela(monkeypatch):
    monkeypatch.setenv("LLM_PRECO_ENTRADA_USD_MTOK", "3")
    monkeypatch.setenv("LLM_PRECO_SAIDA_USD_MTOK", "15")
    monkeypatch.setenv("USD_BRL", "5")

    @trace("classificar")
    def classificar():
        registrar_uso(1_000_000, 0, custo_brl=0.01)

    with processo_atual("p6"):
        classificar()
    assert resumo_custo("p6").custo_brl == pytest.approx(0.01)


def test_data_do_passo_segue_o_relogio_simulado():
    avancar_tempo(10)

    @trace("x")
    def x():
        pass

    with processo_atual("p7"):
        x()
    assert listar_passos("p7")[0].em.date() == date(2026, 11, 23)


def test_registrar_uso_fora_de_trace_nao_quebra():
    registrar_uso(10, 10, decisao="nada")


def test_traces_aninhados_ficam_separados():
    @trace("interno")
    def interno():
        registrar_uso(10, 1)

    @trace("externo")
    def externo():
        registrar_uso(100, 10)
        interno()

    with processo_atual("p8"):
        externo()
    passos = {p.passo: p for p in listar_passos("p8")}
    assert passos["interno"].tokens_entrada == 10
    assert passos["externo"].tokens_entrada == 100
    resumo = resumo_custo("p8")
    assert resumo.passos == 2 and resumo.tokens_entrada == 110
