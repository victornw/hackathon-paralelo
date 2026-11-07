import json
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

from app.portal_sim.mensagens import mensagens
from app.schemas import Etapa, Processo

RAIZ = Path(__file__).resolve().parents[3]
PROIBIDAS = ("unifilar", "DPS", "Ceará", "Enel CE")


def _carteira(pid: str) -> Processo:
    dados = json.loads((RAIZ / "fixtures" / "carteira_demo.json").read_text())
    return Processo.model_validate(next(d for d in dados if d["id"] == pid))


def _fixture(nome: str) -> Processo:
    return Processo.model_validate_json((RAIZ / "fixtures" / nome).read_text())


def _canal(msgs, canal):
    return [m for m in msgs if m.canal == canal]


def test_cliente_uma_mensagem_por_evento_com_primeiro_nome():
    p = _carteira("proc-demo-007")
    cli = _canal(mensagens(p, date(2026, 11, 13)), "cliente")
    assert len(cli) == len(p.eventos)
    assert all("Pedro" in m.texto for m in cli)
    assert "liberado para gerar energia" in cli[-1].texto
    assert "medidor bidirecional" in cli[-2].texto


def test_cliente_sem_titular_usa_ola():
    p = _carteira("proc-demo-004")
    p.campos.pop("titular")
    cli = _canal(mensagens(p, date(2026, 11, 13)), "cliente")
    assert cli[0].texto.startswith("Olá!")
    assert "GD-" in cli[0].texto or p.eventos[0].numero_solicitacao in cli[0].texto


def test_cliente_pendencia_e_reenvio():
    p = _fixture("processo_protocolado.json")
    p.eventos.append(p.eventos[0].model_copy(update={"data": date(2026, 11, 14)}))
    cli = _canal(mensagens(p, date(2026, 11, 14)), "cliente")
    assert "enviamos o pedido de ligação" in cli[0].texto.lower()
    assert "nada muda para você" in cli[1].texto
    assert "de novo" in cli[2].texto


def test_cliente_sem_palavras_proibidas():
    for pid in ("proc-demo-004", "proc-demo-005", "proc-demo-006", "proc-demo-007"):
        for m in _canal(mensagens(_carteira(pid), date(2026, 11, 13)), "cliente"):
            assert not any(w.lower() in m.texto.lower() for w in PROIBIDAS), m.texto
    p = _fixture("processo_protocolado.json")
    for m in _canal(mensagens(p, date(2026, 11, 13)), "cliente"):
        assert not any(w.lower() in m.texto.lower() for w in PROIBIDAS), m.texto


def test_vistoria_cita_so_o_prazo_da_norma():
    p = _carteira("proc-demo-006")
    cli = _canal(mensagens(p, date(2026, 11, 13)), "cliente")
    msg = next(m for m in cli if m.tipo == "vistoria_solicitada")
    assert "Pela norma, a Enel tem até 12/11/2026 para vistoriar e ligar" in msg.texto
    assert msg.texto.count("/2026") == 1


def test_pendencia_integrador_com_motivo_correcao_e_link():
    p = _fixture("processo_protocolado.json")
    msg = next(
        m
        for m in mensagens(p, date(2026, 11, 13))
        if m.canal == "integrador" and m.tipo == "pendencia"
    )
    assert "Diagrama unifilar não apresenta o DPS" in msg.texto
    assert "Correção proposta:" in msg.texto
    assert "classificação automática" in msg.texto
    assert msg.link_texto == "Abrir no portal"
    assert quote("integrador@exemplo.com", safe="") in msg.link
    assert msg.link.startswith("/portal-gd/consulta?")


def test_pendencia_com_categoria_do_evento_nao_diz_automatica():
    p = _fixture("processo_protocolado.json")
    ev = p.eventos[-1]
    ev.categoria_pendencia = "unifilar_inconsistente"
    ev.correcao_proposta = "Incluir o DPS no diagrama."
    msg = next(m for m in mensagens(p, date(2026, 11, 13)) if m.tipo == "pendencia")
    assert "Incluir o DPS no diagrama." in msg.texto
    assert "automática" not in msg.texto


def test_perguntas_abertas_do_integrador():
    p = _fixture("processo_exemplo.json")
    msgs = mensagens(p, date(2026, 11, 13))
    perguntas = [m for m in msgs if m.tipo == "pergunta"]
    esperados = [q.id for q in p.perguntas if q.destinatario == "integrador"]
    assert [m.pergunta_id for m in perguntas] == esperados
    assert esperados
    assert all(m.data == date(2026, 11, 13) and m.autor == "agente" for m in perguntas)
    textos_eng = [q.texto for q in p.perguntas if q.destinatario == "engenheiro"]
    assert all(m.texto not in textos_eng for m in msgs)


def test_pergunta_respondida_gera_resposta_do_integrador():
    p = _fixture("processo_exemplo.json")
    q = next(q for q in p.perguntas if q.destinatario == "integrador")
    q.resposta = "Disjuntor de 50 A."
    q.respondida_em = datetime(2026, 11, 12, 9, 0)
    msgs = [m for m in mensagens(p, date(2026, 11, 13)) if m.pergunta_id == q.id]
    assert [m.autor for m in msgs] == ["agente", "integrador"]
    assert msgs[1].texto == "Disjuntor de 50 A."
    assert msgs[1].data == date(2026, 11, 12)
    assert not any(m.tipo == "pergunta" for m in msgs)


def _prazo_msg(hoje):
    p = _carteira("proc-demo-005")
    return [m for m in mensagens(p, hoje) if m.tipo == "prazo"]


def test_prazo_no_prazo_atencao_e_vencido():
    (normal,) = _prazo_msg(date(2026, 11, 10))
    assert "vence em 17/11/2026 (faltam 5 dias úteis)" in normal.texto
    assert "Norma Enel 7.3.5" in normal.texto
    assert not normal.texto.startswith("Atenção")
    assert normal.data == date(2026, 11, 10)

    (atencao,) = _prazo_msg(date(2026, 11, 13))
    assert atencao.texto.startswith("Atenção: ")
    assert "(faltam 2 dias úteis)" in atencao.texto

    (hoje_,) = _prazo_msg(date(2026, 11, 17))
    assert hoje_.texto.startswith("Atenção: a aprovação do orçamento vence hoje.")

    (vencido,) = _prazo_msg(date(2026, 11, 20))
    assert vencido.texto.startswith(
        "Prazo vencido: a aprovação do orçamento venceu em 17/11/2026."
    )


def test_prazo_da_distribuidora_nao_gera_mensagem_ao_integrador():
    p = _carteira("proc-demo-006")
    assert not [m for m in mensagens(p, date(2026, 11, 13)) if m.tipo == "prazo"]


def test_lembrete_vistoria_so_em_orcamento_aprovado():
    p = _carteira("proc-demo-006")
    assert not [
        m for m in mensagens(p, date(2026, 11, 13)) if m.tipo == "lembrete_vistoria"
    ]
    p.etapa = Etapa.ORCAMENTO_APROVADO
    (lembrete,) = [
        m for m in mensagens(p, date(2026, 11, 13)) if m.tipo == "lembrete_vistoria"
    ]
    assert "vistoria" in lembrete.texto and lembrete.link
    assert lembrete.data == date(2026, 11, 13)


def test_ordenado_por_data():
    for pid in ("proc-demo-005", "proc-demo-006", "proc-demo-007", "proc-exemplo-002"):
        datas = [m.data for m in mensagens(_carteira(pid), date(2026, 11, 13))]
        assert datas == sorted(datas)
