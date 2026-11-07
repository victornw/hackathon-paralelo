from datetime import datetime
from pathlib import Path

import pytest

from app.portal_sim import avancar_tempo
from app.portal_sim.portal import (
    MOTIVO_PENDENCIA_ROTEIRO,
    PortalErro,
    SolicitacaoNaoEncontrada,
    aprovar_orcamento,
    avancar_distribuidora,
    consultar_status,
    montar_formulario,
    protocolar,
    reenviar,
    solicitar_vistoria,
)
from app.portal_sim.prazos import calcular_prazos
from app.schemas import Carga, Etapa, Pergunta, Processo
from app.tracing import listar_passos

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


@pytest.fixture
def pronto() -> Processo:
    """Fixture completa: cargas informadas, perguntas respondidas, revisado."""
    p = Processo.model_validate_json((FIXTURES / "processo_exemplo.json").read_text())
    p.visita.relacao_cargas = [Carga(descricao="Geladeira", potencia_w=250)]
    p.perguntas += [
        Pergunta(
            id="t", campo="telefone", texto="Telefone?", resposta="(85) 90000-0000"
        ),
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


def etapas(eventos):
    return [e.etapa for e in eventos]


def test_formulario_lista_o_que_falta_sem_presumir():
    p = Processo.model_validate_json((FIXTURES / "processo_exemplo.json").read_text())
    with pytest.raises(PortalErro) as e:
        montar_formulario(p)
    msg = str(e.value)
    for campo in (
        "modalidade",
        "telefone",
        "potencia_instalada_uc_kw",
        "qtd_ucs_credito",
    ):
        assert campo in msg


def test_formulario_completo(pronto):
    f = montar_formulario(pronto)
    assert f.codigo_uc == "7000123456"
    assert f.potencia_instalada_geracao_kw == 5.0
    assert f.potencia_instalada_uc_kw == 0.25
    assert f.corrente_disjuntor_a == 50
    assert f.modalidade == "Autoconsumo local"


def test_protocolo_exige_revisao_do_engenheiro(pronto):
    pronto.revisado_por = None
    with pytest.raises(PortalErro, match="engenheiro"):
        protocolar(pronto)


def test_protocolar_gera_numero_sequencial_e_trace(pronto):
    n1 = protocolar(pronto)
    n2 = protocolar(pronto)
    assert n1 == "GD-CE-2026-000001" and n2 == "GD-CE-2026-000002"
    assert [p.passo for p in listar_passos(pronto.id)] == ["protocolar", "protocolar"]


def test_consulta_exige_uc_email_e_numero(pronto):
    n = protocolar(pronto)
    (ev,) = consultar_status("7000123456", "INTEGRADOR@exemplo.com ", n)
    assert ev.etapa == Etapa.PROTOCOLADO
    with pytest.raises(SolicitacaoNaoEncontrada):
        consultar_status("7000123456", "outro@exemplo.com", n)
    with pytest.raises(SolicitacaoNaoEncontrada):
        consultar_status("999", "integrador@exemplo.com", n)
    with pytest.raises(SolicitacaoNaoEncontrada):
        consultar_status("7000123456", "integrador@exemplo.com", "GD-CE-2026-999999")


def test_roteiro_completo_com_pendencia_e_prazos(pronto):
    uc, email = "7000123456", "integrador@exemplo.com"
    n = protocolar(pronto)  # sex 13/11

    avancar_tempo(3)  # seg 16/11
    ev = avancar_distribuidora(n)
    assert (
        ev.etapa == Etapa.PENDENCIA and ev.motivo_pendencia == MOTIVO_PENDENCIA_ROTEIRO
    )

    with pytest.raises(PortalErro, match="Aguardando o integrador"):
        avancar_distribuidora(n)
    with pytest.raises(PortalErro, match="indisponível"):
        aprovar_orcamento(n)

    avancar_tempo(1)
    reenviar(n, "unifilar com DPS")
    avancar_tempo(4)
    assert avancar_distribuidora(n).etapa == Etapa.ORCAMENTO_EMITIDO  # sem 2ª pendência

    pronto.eventos = consultar_status(uc, email, n)
    (prazo,) = calcular_prazos(pronto)
    assert prazo.tipo == "aprovar_orcamento" and prazo.conta_contra == "integrador"

    aprovar_orcamento(n)
    solicitar_vistoria(n)
    for esperado in (Etapa.VISTORIA, Etapa.MEDIDOR, Etapa.CONCLUIDO):
        assert avancar_distribuidora(n).etapa == esperado
    with pytest.raises(PortalErro):
        avancar_distribuidora(n)

    assert etapas(consultar_status(uc, email, n)) == [
        Etapa.PROTOCOLADO,
        Etapa.PENDENCIA,
        Etapa.PROTOCOLADO,
        Etapa.ORCAMENTO_EMITIDO,
        Etapa.ORCAMENTO_APROVADO,
        Etapa.VISTORIA_SOLICITADA,
        Etapa.VISTORIA,
        Etapa.MEDIDOR,
        Etapa.CONCLUIDO,
    ]


def test_roteiro_sem_pendencia(pronto):
    n = protocolar(pronto, com_pendencia=False)
    assert avancar_distribuidora(n).etapa == Etapa.ORCAMENTO_EMITIDO
