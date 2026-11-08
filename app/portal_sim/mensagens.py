"""Mensagens do chat simulado: canal do integrador e canal do cliente final.

Tudo determinístico, derivado do Processo (eventos, perguntas, prazos).
Regras de conteúdo: nada inventado; prazo da distribuidora só aparece como
"prazo da norma" com a data calculada em prazos.py; sem jargão no canal do cliente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal
from urllib.parse import urlencode

from app.portal_sim.pendencias import CATEGORIAS, classificar_por_palavras
from app.portal_sim.prazos import prazos_dos_eventos, situacao
from app.schemas import Etapa, EventoPortal, Processo


@dataclass
class Mensagem:
    canal: Literal["integrador", "cliente"]
    data: date
    autor: Literal["agente", "integrador"]
    texto: str
    tipo: str
    pergunta_id: str | None = None
    link: str | None = None
    link_texto: str | None = None


_ROTULO_PRAZO = {
    "orcamento": "Emissão do orçamento pela distribuidora",
    "aprovar_orcamento": "A aprovação do orçamento",
    "devolver_contratos": "A devolução dos contratos",
    "sanar_pendencia": "A correção da pendência",
    "vistoria_ligacao": "Vistoria e ligação pela distribuidora",
}


def _br(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _valor(processo: Processo, chave: str) -> str | None:
    c = processo.campos.get(chave)
    if c is None or c.valor is None or str(c.valor).strip() == "":
        return None
    return str(c.valor).strip()


def _saudacao(processo: Processo) -> str:
    titular = _valor(processo, "titular")
    if not titular:
        return "Olá"
    return f"Olá, {titular.split()[0].title()}"


def _link_portal(processo: Processo, numero: str | None) -> str:
    uc = _valor(processo, "uc")
    if uc and processo.email_contato and numero:
        return "/portal-gd/consulta?" + urlencode(
            {"uc": uc, "email": processo.email_contato, "numero": numero}
        )
    return "/portal-gd"


def _numero(processo: Processo) -> str | None:
    if processo.numero_solicitacao:
        return processo.numero_solicitacao
    for ev in processo.eventos:
        if ev.numero_solicitacao:
            return ev.numero_solicitacao
    return None


def _cliente(
    processo: Processo, ev: EventoPortal, depois_de_pendencia: bool, eventos_ate: list
) -> str | None:
    ola = _saudacao(processo)
    e = ev.etapa
    if e == Etapa.PROTOCOLADO and not depois_de_pendencia:
        return (
            f"{ola}! Enviamos o pedido de ligação do seu sistema solar para a Enel. "
            f"O número da solicitação é {ev.numero_solicitacao}."
        )
    if e == Etapa.PROTOCOLADO:
        return (
            f"{ola}! Enviamos de novo o pedido para a Enel, já com o ajuste feito. "
            f"O número da solicitação continua {ev.numero_solicitacao}."
        )
    if e == Etapa.PENDENCIA:
        return (
            f"{ola}. A Enel pediu um ajuste na documentação. "
            "O ajuste precisa ser concluído antes de a análise continuar."
        )
    if e == Etapa.ORCAMENTO_EMITIDO:
        return (
            f"{ola}! A Enel emitiu o orçamento de conexão do seu sistema. "
            "O integrador vai aprovar o orçamento."
        )
    if e == Etapa.ORCAMENTO_APROVADO:
        return (
            f"{ola}! O orçamento foi aprovado. O próximo passo é a instalação "
            "e o pedido de vistoria à Enel."
        )
    if e == Etapa.VISTORIA_SOLICITADA:
        texto = f"{ola}! Pedimos a vistoria à Enel."
        prazo = next(
            (
                p
                for p in prazos_dos_eventos(eventos_ate)
                if p.tipo == "vistoria_ligacao"
            ),
            None,
        )
        if prazo:
            texto += (
                f" Pela norma, a Enel tem até {_br(prazo.vencimento)} "
                "para vistoriar e ligar."
            )
        return texto
    if e == Etapa.VISTORIA:
        return f"{ola}! A Enel fez a vistoria do seu sistema."
    if e == Etapa.MEDIDOR:
        return f"{ola}! O medidor bidirecional já foi instalado."
    if e == Etapa.CONCLUIDO:
        return f"{ola}! Tudo certo: seu sistema está liberado para gerar energia."
    return None


def _canal_cliente(processo: Processo) -> list[Mensagem]:
    saida: list[Mensagem] = []
    eventos = sorted(processo.eventos, key=lambda e: e.data)
    teve_pendencia = False
    for i, ev in enumerate(eventos):
        texto = _cliente(processo, ev, teve_pendencia, eventos[: i + 1])
        if ev.etapa == Etapa.PENDENCIA:
            teve_pendencia = True
        if texto:
            saida.append(Mensagem("cliente", ev.data, "agente", texto, ev.etapa.value))
    return saida


def _texto_pendencia(ev: EventoPortal) -> str:
    motivo = ev.motivo_pendencia or ev.descricao
    chave = ev.categoria_pendencia
    automatica = False
    if chave not in CATEGORIAS:
        chave = classificar_por_palavras(motivo)
        automatica = True
    cat = CATEGORIAS[chave]
    correcao = ev.correcao_proposta or cat["correcao"]
    if ev.correcao_proposta:
        automatica = False
    if automatica:
        correcao += " (classificação automática)"
    return (
        f"A Enel abriu uma pendência. Motivo do analista: “{motivo.rstrip('.')}.” "
        f"Categoria: {cat['descricao']}. Correção proposta: {correcao}"
    )


# Aviso ao integrador quando o portal muda de etapa (a pendência tem texto próprio).
_AVISO_ETAPA = {
    Etapa.PROTOCOLADO: "Pedido protocolado na Enel. Agora é aguardar a análise da distribuidora.",
    Etapa.ORCAMENTO_EMITIDO: "A Enel emitiu o orçamento de conexão. Aprove no portal para o processo seguir.",
    Etapa.ORCAMENTO_APROVADO: "Orçamento aprovado no portal.",
    Etapa.VISTORIA_SOLICITADA: "Vistoria solicitada. Agora é aguardar a vistoria e a ligação pela distribuidora.",
    Etapa.VISTORIA: "A Enel registrou a vistoria do sistema.",
    Etapa.MEDIDOR: "A Enel registrou a instalação do medidor bidirecional.",
    Etapa.CONCLUIDO: "Processo concluído. O sistema está liberado para gerar energia.",
}


def _canal_integrador(processo: Processo, hoje: date) -> list[Mensagem]:
    saida: list[Mensagem] = []
    for q in processo.perguntas:
        if q.id.startswith("falha:") and not q.resposta:
            saida.append(Mensagem(
                "integrador", hoje, "agente", q.texto, "falha",
                link=f"/processos/{processo.id}", link_texto="Ver erro e tentar de novo",
            ))
            continue
        if q.destinatario != "integrador":
            continue
        if not q.resposta:
            saida.append(
                Mensagem(
                    "integrador", hoje, "agente", q.texto, "pergunta", pergunta_id=q.id
                )
            )
        else:
            quando = q.respondida_em.date() if q.respondida_em else hoje
            saida.append(
                Mensagem(
                    "integrador",
                    quando,
                    "agente",
                    q.texto,
                    "pergunta_respondida",
                    pergunta_id=q.id,
                )
            )
            saida.append(
                Mensagem(
                    "integrador",
                    quando,
                    "integrador",
                    q.resposta,
                    "resposta",
                    pergunta_id=q.id,
                )
            )

    if processo.etapa == Etapa.EM_REVISAO:
        abertas = [q for q in processo.perguntas if not q.resposta]
        texto = "O processo está em revisão. Confira os documentos antes de aprovar e assinar."
        if abertas:
            texto += " Ainda há confirmações pendentes; a revisão mostra o que falta."
        saida.append(Mensagem(
            "integrador", hoje, "agente", texto, "revisao",
            link=f"/processos/{processo.id}/revisao", link_texto="Abrir revisão",
        ))

    eventos = sorted(processo.eventos, key=lambda e: e.data)
    for ev in eventos:
        if ev.etapa == Etapa.PENDENCIA:
            saida.append(
                Mensagem(
                    "integrador",
                    ev.data,
                    "agente",
                    _texto_pendencia(ev),
                    "pendencia",
                    link=_link_portal(processo, ev.numero_solicitacao),
                    link_texto="Abrir no portal",
                )
            )
        elif texto := _AVISO_ETAPA.get(ev.etapa):
            if ev.numero_solicitacao:
                texto += f" Solicitação: {ev.numero_solicitacao}."
            atual = ev is eventos[-1] and processo.etapa == ev.etapa
            saida.append(Mensagem(
                "integrador", ev.data, "agente", texto, ev.etapa.value,
                link=_link_portal(processo, ev.numero_solicitacao) if atual else None,
                link_texto="Abrir no portal" if atual else None,
            ))

    for prazo in prazos_dos_eventos(processo.eventos):
        sit, restantes = situacao(prazo, hoje)
        if prazo.conta_contra != "integrador":
            # Prazo da Enel: só vira mensagem quando ela passa do limite.
            if sit == "vencido":
                rotulo = _ROTULO_PRAZO[prazo.tipo]
                saida.append(
                    Mensagem(
                        "integrador", hoje, "agente",
                        f"A Enel passou do prazo: {rotulo[0].lower()}{rotulo[1:]} "
                        f"venceu em {_br(prazo.vencimento)}. Vale cobrar a distribuidora "
                        f"citando o número da solicitação. Fonte: {prazo.fonte}.",
                        "prazo_enel",
                        link=_link_portal(processo, _numero(processo)),
                        link_texto="Abrir no portal",
                    )
                )
            continue
        unidade = "dia útil" if prazo.dias_uteis else "dia"
        if restantes != 1:
            unidade = "dias úteis" if prazo.dias_uteis else "dias"
        rotulo = _ROTULO_PRAZO[prazo.tipo]
        if sit == "vencido":
            texto = (
                f"Prazo vencido: {rotulo[0].lower()}{rotulo[1:]} "
                f"venceu em {_br(prazo.vencimento)}."
            )
        elif sit == "vence_hoje":
            texto = f"Atenção: {rotulo[0].lower()}{rotulo[1:]} vence hoje."
        else:
            texto = (
                f"{rotulo} vence em {_br(prazo.vencimento)} "
                f"(faltam {restantes} {unidade})."
            )
            if sit == "atencao":
                texto = f"Atenção: {texto[0].lower()}{texto[1:]}"
        saida.append(
            Mensagem(
                "integrador", hoje, "agente", f"{texto} Fonte: {prazo.fonte}.", "prazo",
                link=_link_portal(processo, _numero(processo)), link_texto="Abrir no portal"
            )
        )

    if processo.etapa == Etapa.ORCAMENTO_APROVADO:
        saida.append(
            Mensagem(
                "integrador",
                hoje,
                "agente",
                "Orçamento aprovado. A instalação já terminou? Se sim, solicite a "
                "vistoria agora no portal.",
                "lembrete_vistoria",
                link=_link_portal(processo, _numero(processo)),
                link_texto="Abrir no portal",
            )
        )
    return saida


def mensagens(processo: Processo, hoje: date) -> list[Mensagem]:
    """Todas as mensagens do processo, ordenadas por data (estável)."""
    todas = _canal_integrador(processo, hoje) + _canal_cliente(processo)
    return sorted(todas, key=lambda m: m.data)
