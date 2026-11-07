"""Telas do Dev B: painel da carteira e timeline do processo.

Uso no main.py:  app.include_router(painel.router); app.mount("/static", ...)
Os processos vêm da tabela `processos(id, json)` quando ela existir; antes disso,
de fixtures/carteira_demo.json.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
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
    return templates.TemplateResponse(
        request,
        "painel.html",
        {
            "colunas": colunas,
            "hoje": dia,
            "total": len(processos),
            "vencendo": vencendo,
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
        },
    )
