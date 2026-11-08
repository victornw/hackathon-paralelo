import json

import pytest

from app.core import perguntas
from app.core.arranjo import bitola_por_tabela
from app.schemas import Pergunta, Processo
from evals import processo_completo as pc

FIXTURES = pc.RAIZ / "fixtures"


@pytest.fixture
def processo() -> Processo:
    return Processo.model_validate_json(
        (FIXTURES / "processo_exemplo.json").read_text()
    )


@pytest.fixture
def gabarito() -> dict:
    return json.loads((pc.CONTAS / "cliente_1_gabarito.json").read_text())


def test_toda_exigencia_do_integrador_tem_resposta():
    campos = {e.campo for e in perguntas.EXIGENCIAS if e.destinatario == "integrador"}
    assert campos <= pc.RESPOSTAS.keys()


def test_campos_da_conta_vem_do_gabarito(processo, gabarito):
    contexto = pc.Contexto(gabarito, processo)
    assert pc.RESPOSTAS["campos.uc"](contexto) == "12345678"
    assert pc.RESPOSTAS["campos.tensao_atendimento_v"](contexto) == "220"
    assert pc.RESPOSTAS["campos.tipo_ligacao"](contexto) == "monofasico"


def test_bitola_segue_a_tabela_do_agente(processo, gabarito):
    processo.visita.disjuntor_ca_a = 25
    resposta = pc.RESPOSTAS["bitola_ca_mm2"](pc.Contexto(gabarito, processo))
    assert float(resposta) == bitola_por_tabela(25)


def test_strings_confirma_sugestao_ou_reparte_modulos(processo, gabarito):
    contexto = pc.Contexto(gabarito, processo)
    processo.kit.strings = [processo.kit.strings[0]]
    assert pc.RESPOSTAS["strings"](contexto) == "sim"
    processo.kit.strings = []
    processo.kit.inversor.num_mppt = 3
    gabarito["kit"]["qtd_modulos"] = 10
    assert pc.RESPOSTAS["strings"](contexto) == "4, 3, 3"


def _pergunta(
    id_: str, campo: str, destinatario="integrador", resposta=None
) -> Pergunta:
    return Pergunta(
        id=id_, campo=campo, texto="?", destinatario=destinatario, resposta=resposta
    )


def test_a_responder_separa_mapeadas_de_desconhecidas(processo):
    processo.perguntas = [
        _pergunta("telefone", "telefone"),
        _pergunta("qtd_ucs_credito", "qtd_ucs_credito", resposta="1"),
        _pergunta("kit:modulo", "kit.modulo"),
        _pergunta("lembrete:orcamento_emitido", "aprovar_orcamento"),
        _pergunta("falha:conferir", "falha:conferir", "engenheiro"),
        _pergunta("strings", "strings", "engenheiro"),
        _pergunta("pendencia:2026-11-09", "pendencia", "engenheiro"),
    ]
    respondiveis, sem_mapa = pc.a_responder(processo)
    assert [q.id for q in respondiveis] == ["telefone", "strings"]
    assert [q.id for q in sem_mapa] == ["kit:modulo"]


def test_montar_respostas_usa_o_id_da_pergunta(processo, gabarito):
    processo.perguntas = [_pergunta("telefone", "telefone")]
    assert pc.montar_respostas(processo, gabarito) == [
        {"id": "telefone", "resposta": "(85) 90000-0000"}
    ]
