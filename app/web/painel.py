"""Telas do Dev B: painel da carteira e timeline do processo.

Uso no main.py:  app.include_router(painel.router); app.mount("/static", ...)
Os processos vêm da tabela `processos(id, json)` quando ela existir; antes disso,
de fixtures/carteira_demo.json.

Bloco "Documentos gerados" (para a tela do engenheiro, Dev A). Duas formas:
1. Include server-side, usando o mesmo diretório de templates (app/web/templates):
       {% include "_documentos.html" %}
   com o contexto de `contexto_documentos(processo)` mesclado ao da página, ou
   seja `{**seu_contexto, **contexto_documentos(p)}`.
2. HTMX, sem tocar no contexto:
       <div hx-get="/processos/{{ p.id }}/documentos" hx-trigger="load"></div>
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates

from app.portal_sim.prazos import calcular_prazos, situacao
from app.portal_sim.relogio import hoje
from app.schemas import Etapa, Prazo, Processo
from app.tracing import listar_passos_detalhados, resumo_custo
from app.tracing.db import conectar

RAIZ = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
router = APIRouter()

ROTULOS = {
    Etapa.MONTAGEM: "Montagem",
    Etapa.EM_REVISAO: "Em revisão",
    Etapa.PROTOCOLADO: "Protocolado",
    Etapa.PENDENCIA: "Pendência",
    Etapa.ORCAMENTO_EMITIDO: "Orçamento emitido",
    Etapa.ORCAMENTO_APROVADO: "Orçamento aprovado",
    Etapa.VISTORIA_SOLICITADA: "Vistoria solicitada",
    Etapa.VISTORIA: "Vistoria",
    Etapa.MEDIDOR: "Medidor",
    Etapa.CONCLUIDO: "Concluído",
}
ROTULO_PRAZO = {
    "orcamento": "Distribuidora emitir o orçamento",
    "aprovar_orcamento": "Aprovar o orçamento",
    "devolver_contratos": "Devolver os contratos",
    "sanar_pendencia": "Sanar a pendência",
    "vistoria_ligacao": "Distribuidora vistoriar e ligar",
}


def carregar_processos() -> list[Processo]:
    try:
        with conectar() as con:
            linhas = con.execute("SELECT json FROM processos").fetchall()
        if linhas:
            return [Processo.model_validate_json(j) for (j,) in linhas]
    except sqlite3.OperationalError:
        pass  # tabela do Dev A ainda não existe
    dados = json.loads((RAIZ / "fixtures" / "carteira_demo.json").read_text())
    return [Processo.model_validate(d) for d in dados]


@dataclass
class PrazoTela:
    prazo: Prazo
    rotulo: str
    situacao: str
    restantes: int
    fracao: float  # quanto do prazo já correu, 0..1

    @classmethod
    def de(cls, prazo: Prazo, dia: date) -> PrazoTela:
        sit, restantes = situacao(prazo, dia)
        total = (prazo.vencimento - prazo.inicio).days or 1
        corrido = (dia - prazo.inicio).days
        return cls(
            prazo,
            ROTULO_PRAZO[prazo.tipo],
            sit,
            restantes,
            max(0.0, min(1.0, corrido / total)),
        )


def _campo(p: Processo, chave: str) -> str:
    c = p.campos.get(chave)
    return "—" if c is None or c.valor is None else str(c.valor)


def _cartao(p: Processo, dia: date) -> dict:
    prazos = [PrazoTela.de(pr, dia) for pr in calcular_prazos(p)]
    return {
        "p": p,
        "titular": _campo(p, "titular").title(),
        "uc": _campo(p, "uc"),
        "kwp": (p.kit.potencia_total_wp / 1000) if p.kit else None,
        "prazos": prazos,
        "integrador": [x for x in prazos if x.prazo.conta_contra == "integrador"],
        "incertas": sum(
            1 for r in p.regras if r.status.value in ("incerta", "reprovada")
        ),
        "perguntas": sum(1 for q in p.perguntas if not q.resposta),
    }


def contexto_documentos(processo: Processo) -> dict:
    """Contexto do parcial `_documentos.html` (para quem faz o include)."""
    return {"processo_id": processo.id, "documentos": processo.documentos}


ACAO_PRAZO = {
    "orcamento": "emitir o orçamento de",
    "aprovar_orcamento": "aprovar o orçamento de",
    "devolver_contratos": "devolver os contratos de",
    "sanar_pendencia": "corrigir a pendência de",
    "vistoria_ligacao": "vistoriar e ligar o sistema de",
}

_ORDEM_SITUACAO = {"vencido": 0, "vence_hoje": 1, "atencao": 2, "no_prazo": 3}


def proximos_prazos(
    processos: list[Processo], dia: date, limite: int = 6
) -> list[dict]:
    """Prazos correndo na carteira, do mais urgente para o menos urgente."""
    itens = []
    for p in processos:
        for pr in calcular_prazos(p):
            x = PrazoTela.de(pr, dia)
            itens.append(
                {
                    "x": x,
                    "titular": _campo(p, "titular").title(),
                    "acao": ACAO_PRAZO[pr.tipo],
                    "quem": "Integrador" if pr.conta_contra == "integrador" else "Enel",
                    "link": f"/processos/{p.id}/chat"
                    if pr.conta_contra == "integrador"
                    else f"/processos/{p.id}/timeline",
                }
            )
    itens.sort(
        key=lambda i: (_ORDEM_SITUACAO[i["x"].situacao], i["x"].prazo.vencimento)
    )
    return itens[:limite]


AGORA = {
    Etapa.MONTAGEM: "montando o pacote",
    Etapa.EM_REVISAO: "esperando a revisão do engenheiro",
    Etapa.PROTOCOLADO: "esperando a análise da Enel",
    Etapa.PENDENCIA: "corrigindo a pendência da Enel",
    Etapa.ORCAMENTO_EMITIDO: "esperando o integrador aprovar o orçamento",
    Etapa.ORCAMENTO_APROVADO: "acompanhando os contratos",
    Etapa.VISTORIA_SOLICITADA: "esperando a Enel vistoriar",
    Etapa.VISTORIA: "acompanhando a vistoria",
    Etapa.MEDIDOR: "esperando a troca do medidor",
    Etapa.CONCLUIDO: "sistema conectado à rede",
}


def _passos_etapa(atual: Etapa) -> list[dict]:
    """Trilho de etapas do processo em foco. Pendência é desvio: só aparece
    quando o processo está nela."""
    ordem = [e for e in Etapa if e != Etapa.PENDENCIA or atual == Etapa.PENDENCIA]
    i = ordem.index(atual)
    return [
        {
            "rotulo": ROTULOS[e],
            "estado": "feito" if j < i else "atual" if j == i else "futuro",
        }
        for j, e in enumerate(ordem)
    ]


def _foco(p: Processo, dia: date) -> dict:
    from app.portal_sim.mensagens import mensagens
    from app.web.processo import _contexto

    ctx = _contexto(p)
    cidade = p.campos.get("cidade")
    ligacao = p.campos.get("tipo_ligacao")
    agora = AGORA[p.etapa]
    if ctx["trabalhando"]:
        agora = "lendo os documentos e montando o pacote"
    elif ctx["abertas"]:
        agora = "esperando resposta do integrador"
    msgs = mensagens(p, dia)
    return {
        **ctx,
        "c": _cartao(p, dia),
        "cidade": str(cidade.valor).title() if cidade and cidade.valor else None,
        "ligacao": str(ligacao.valor) if ligacao and ligacao.valor else None,
        "agora": agora,
        "trilho": _passos_etapa(p.etapa),
        "registro": listar_passos_detalhados(p.id)[-8:],
        "conversa": [m for m in msgs if m.canal == "integrador"],
        "conversa_cliente": [m for m in msgs if m.canal == "cliente"],
    }


@router.get("/painel")
def painel(request: Request, tarefas: BackgroundTasks, p: str | None = None):
    dia = hoje()
    processos = sorted(carregar_processos(), key=lambda x: list(Etapa).index(x.etapa))
    cartoes = [_cartao(x, dia) for x in processos]
    vencendo = sum(
        1
        for k in cartoes
        for x in k["integrador"]
        if x.situacao in ("atencao", "vence_hoje", "vencido")
    )
    foco = next((x for x in processos if x.id == p), None) or next(
        (x for x in processos if x.etapa == Etapa.EM_REVISAO),
        processos[0] if processos else None,
    )
    f = _foco(foco, dia) if foco else None
    if f and f["trabalhando"]:
        from app.core import orquestrador

        tarefas.add_task(orquestrador.orquestrar, foco.id)
    return templates.TemplateResponse(
        request,
        "painel.html",
        {
            "cartoes": cartoes,
            "rotulos": ROTULOS,
            "hoje": dia,
            "total": len(processos),
            "vencendo": vencendo,
            "proximos": proximos_prazos(processos, dia),
            "f": f,
        },
    )


# Marcos que a timeline mostra por padrão; o resto (decisões internas, chamadas ao
# modelo, consultas repetidas ao portal) fica em "Ver detalhes técnicos".
MARCOS = {
    "extrair_conta": "Leu a conta de luz",
    "extrair_kit": "Leu a proposta do kit",
    "extrair_padrao": "Leu a foto do padrão de entrada",
    "verificar_arranjo": "Conferiu o arranjo do kit",
    "perguntar": "Perguntou o que faltava",
    "gerar_documentos": "Gerou os documentos",
    "conferir": "Conferiu contra a norma da Enel",
    "enviar_revisao": "Enviou para a revisão do engenheiro",
    "revisao_engenheiro": "Engenheiro revisou e assinou",
    "protocolar": "Protocolou no portal da Enel",
    "tratar_pendencia": "Tratou a pendência da Enel",
    "reenviar": "Reenviou a correção",
}


def _so_marcos(itens: list[dict]) -> list[dict]:
    """Marcos e falhas; de uma sequência do mesmo marco fica só a última vez."""
    saida: list[dict] = []
    for i in itens:
        if i["tipo"] == "agente":
            if i["passo"].passo not in MARCOS and not i["passo"].erro:
                continue
            i = {**i, "titulo": MARCOS.get(i["passo"].passo, i["titulo"])}
            if (
                saida
                and saida[-1]["tipo"] == "agente"
                and saida[-1]["passo"].passo == i["passo"].passo
                and not i["passo"].erro
            ):
                saida[-1] = i
                continue
        saida.append(i)
    return saida


@router.get("/processos/{processo_id}/timeline")
def timeline(request: Request, processo_id: str, detalhes: bool = False):
    dia = hoje()
    proc = next((p for p in carregar_processos() if p.id == processo_id), None)
    if proc is None:
        raise HTTPException(404, "Processo não encontrado.")
    itens = [
        {"quando": ev.data, "tipo": "portal", "titulo": ROTULOS[ev.etapa], "ev": ev}
        for ev in proc.eventos
    ] + [
        {
            "quando": ps.passo.em.date(),
            "tipo": "agente",
            "titulo": ps.passo.passo,
            "passo": ps.passo,
            "prompts": ps.prompts,
        }
        for ps in listar_passos_detalhados(processo_id)
    ]
    itens.sort(key=lambda i: (i["quando"], i["tipo"] == "portal"))
    total = len(itens)
    if not detalhes:
        itens = _so_marcos(itens)
    return templates.TemplateResponse(
        request,
        "timeline.html",
        {
            "detalhes": detalhes,
            "total": total,
            "c": _cartao(proc, dia),
            "itens": itens,
            "resumo": resumo_custo(processo_id),
            "hoje": dia,
            "rotulos": ROTULOS,
            **contexto_documentos(proc),
        },
    )


@router.get("/processos/{processo_id}/documentos/{nome}/ver")
def ver_documento(processo_id: str, nome: str):
    """Abre o PDF ou SVG no navegador (inline), em vez de baixar."""
    proc = next((p for p in carregar_processos() if p.id == processo_id), None)
    doc = (
        next((d for d in proc.documentos if d.nome_arquivo == nome), None)
        if proc
        else None
    )
    if doc is None or not Path(doc.caminho).is_file():
        raise HTTPException(404, "Documento não encontrado.")
    tipo = "application/pdf" if doc.formato == "pdf" else "image/svg+xml"
    return FileResponse(
        doc.caminho,
        media_type=tipo,
        filename=doc.nome_arquivo,
        content_disposition_type="inline",
    )


@router.get("/processos/{processo_id}/documentos")
def documentos(request: Request, processo_id: str):
    proc = next((p for p in carregar_processos() if p.id == processo_id), None)
    if proc is None:
        raise HTTPException(404, "Processo não encontrado.")
    return templates.TemplateResponse(
        request, "_documentos.html", contexto_documentos(proc)
    )


from app.portal_sim.rotas import router as _portal_router

router.include_router(_portal_router)

from app.web.chat import router as _chat_router

router.include_router(_chat_router)


@router.post("/processos/{processo_id}/regras/R05/confirmar")
def confirmar_r05(processo_id: str, engenheiro: str = Form(...)):
    """Clique do engenheiro na revisão: assume a R05 incerta (registro ativo sem
    tensão no INMETRO e datasheet 220 V). Grava nome e data no resultado."""
    from app.core import repositorio as repo
    from app.core.parecer import r05_inmetro

    try:
        repo.carregar(processo_id)
    except KeyError as exc:
        raise HTTPException(404, "Processo não encontrado.") from exc
    try:
        atualizado = repo.atualizar(
            processo_id, lambda p: r05_inmetro.confirmar(p, engenheiro)
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    r05 = next(r for r in atualizado.regras if r.regra_id == "R05")
    return {"confirmado_por": r05.confirmado_por, "confirmado_em": r05.confirmado_em}


# Telas de novo processo, detalhe e revisão do engenheiro
from app.web.processo import router as _processo_router
from app.web.revisao import router as _revisao_router

router.include_router(_processo_router)
router.include_router(_revisao_router)

from app.web.saude import router as _saude_router

router.include_router(_saude_router)

from app.web.metricas import router as _metricas_router

router.include_router(_metricas_router)
