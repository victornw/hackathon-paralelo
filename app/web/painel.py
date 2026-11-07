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

from fastapi import APIRouter, Form, HTTPException, Request
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


@router.get("/painel")
def painel(request: Request):
    dia = hoje()
    processos = carregar_processos()
    colunas = [
        {
            "etapa": e,
            "rotulo": ROTULOS[e],
            "cartoes": [_cartao(p, dia) for p in processos if p.etapa == e],
        }
        for e in Etapa
    ]
    vencendo = sum(
        1
        for c in colunas
        for k in c["cartoes"]
        for x in k["integrador"]
        if x.situacao in ("atencao", "vence_hoje", "vencido")
    )
    proximos = proximos_prazos(processos, dia)
    return templates.TemplateResponse(
        request,
        "painel.html",
        {
            "colunas": colunas,
            "hoje": dia,
            "total": len(processos),
            "vencendo": vencendo,
            "proximos": proximos,
        },
    )


@router.get("/processos/{processo_id}/timeline")
def timeline(request: Request, processo_id: str):
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
    return templates.TemplateResponse(
        request,
        "timeline.html",
        {
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
