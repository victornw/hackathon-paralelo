"""Tela de revisão do engenheiro: pacote gerado, regras com fonte, dúvidas e aprovação."""

from __future__ import annotations

import io
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.core import orquestrador
from app.core import repositorio as repo
from app.core.aprovacao import bloqueios_aprovacao
from app.portal_sim.relogio import hoje
from app.schemas import Etapa, PassoTrace, Processo, StatusRegra
from app.tracing import listar_passos
from app.tracing.trace import gravar_passo
from app.web.painel import ROTULOS, contexto_documentos

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
router = APIRouter()

PASSO = "revisao_engenheiro"
CHAVES_INTERNAS = {"confirmavel", "chave_confirmacao"}
ROTULO_STATUS = {
    "aprovada": "Aprovada",
    "reprovada": "Reprovada",
    "incerta": "Incerta",
    "nao_verificada": "Não verificada",
}


class TempoRevisao(BaseModel):
    segundos: int = Field(ge=1, le=14400)
    resultado: Literal["aprovado", "devolvido"]


def minutos_de_revisao(processo_id: str) -> list[float]:
    return [p.ms / 60000 for p in listar_passos(processo_id) if p.passo == PASSO]


def _ordem(regra_id: str) -> tuple[int, str]:
    return (0, regra_id) if regra_id == "R00" else (1, regra_id)


def _campo(p: Processo, chave: str) -> str:
    c = p.campos.get(chave)
    return str(c.valor) if c is not None and c.valor else "—"


def _valores(regra) -> list[tuple[str, str]]:
    return [
        (str(k), str(v)) for k, v in regra.valores.items() if k not in CHAVES_INTERNAS
    ]


def contar(p: Processo) -> dict[str, int]:
    return {
        "aprovadas": sum(r.status == StatusRegra.APROVADA for r in p.regras),
        "premissa": sum(bool(r.premissas) for r in p.regras),
        "alertas": sum(bool(r.alertas) for r in p.regras),
        "incertas": sum(r.status == StatusRegra.INCERTA for r in p.regras),
        "reprovadas": sum(r.status == StatusRegra.REPROVADA for r in p.regras),
        "nao_verificadas": sum(
            r.status == StatusRegra.NAO_VERIFICADA for r in p.regras
        ),
    }


@router.get("/processos/{processo_id}/revisao")
def revisao(request: Request, processo_id: str, tarefas: BackgroundTasks):
    try:
        p = repo.carregar(processo_id)
    except KeyError as exc:
        raise HTTPException(404, "Processo não encontrado.") from exc
    regras = sorted(p.regras, key=lambda r: _ordem(r.regra_id))
    kwp = (p.kit.potencia_total_wp / 1000) if p.kit else None
    bloqueios = bloqueios_aprovacao(p)
    trabalhando = orquestrador.trabalhando(p)
    if trabalhando:
        tarefas.add_task(orquestrador.orquestrar, p.id)
    return templates.TemplateResponse(
        request,
        "processo_revisao.html",
        {
            "p": p,
            "titular": _campo(p, "titular").title(),
            "uc": _campo(p, "uc"),
            "kwp": kwp,
            "etapa_rotulo": ROTULOS.get(p.etapa, p.etapa.value),
            "revisavel": p.etapa == Etapa.PENDENCIA
            or (p.etapa == Etapa.EM_REVISAO and not p.revisado_por),
            "trabalhando": trabalhando,
            "aguardando_protocolo": orquestrador.aguardando_protocolo(p),
            "regras": [
                {
                    "r": r,
                    "valores": _valores(r),
                    "rotulo": ROTULO_STATUS[r.status.value],
                    "confirmavel": r.regra_id == "R05"
                    and r.status == StatusRegra.INCERTA
                    and r.valores.get("confirmavel") == "sim"
                    and not r.confirmado_por,
                }
                for r in regras
            ],
            "contagem": contar(p),
            "bloqueios": bloqueios,
            "perguntas": [
                q
                for q in p.perguntas
                if q.destinatario == "engenheiro" and not q.resposta
            ],
            "hoje": hoje(),
            **contexto_documentos(p),
        },
    )


@router.get("/processos/{processo_id}/pacote-para-assinatura.zip")
def pacote_para_assinatura(processo_id: str):
    """PDFs mais recentes do pacote (Anexo A, memorial, unifilar) para o engenheiro
    assinar fora do dia, com certificado ICP-Brasil ou gov.br."""
    try:
        p = repo.carregar(processo_id)
    except KeyError as exc:
        raise HTTPException(404, "Processo não encontrado.") from exc
    ultimos = {}
    for d in sorted(p.documentos, key=lambda d: d.gerado_em):
        if d.formato == "pdf" and Path(d.caminho).is_file():
            ultimos[d.tipo] = d
    if not ultimos:
        raise HTTPException(404, "O pacote ainda não foi gerado.")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for d in ultimos.values():
            z.write(d.caminho, d.nome_arquivo)
    nome = f"pacote-{processo_id}-para-assinatura.zip"
    return Response(
        buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@router.post("/processos/{processo_id}/revisao/tempo", status_code=204)
def registrar_tempo(processo_id: str, corpo: TempoRevisao):
    try:
        repo.carregar(processo_id)
    except KeyError as exc:
        raise HTTPException(404, "Processo não encontrado.") from exc
    minutos = round(corpo.segundos / 60)
    gravar_passo(
        PassoTrace(
            processo_id=processo_id,
            passo=PASSO,
            decisao=f"Revisão do engenheiro: {minutos} min ({corpo.resultado}).",
            ms=corpo.segundos * 1000,
            em=datetime.combine(hoje(), datetime.now().time()),
        )
    )
    return Response(status_code=204)
