"""Chat simulado: canal do integrador e canal do cliente final (WhatsApp simulado)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.templating import Jinja2Templates

from app.portal_sim.mensagens import mensagens
from app.portal_sim.relogio import hoje
from app.web.sugestoes import sugestoes

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
router = APIRouter()


@router.get("/processos/{processo_id}/chat")
def chat(request: Request, processo_id: str):
    from app.web.painel import carregar_processos

    proc = next((p for p in carregar_processos() if p.id == processo_id), None)
    if proc is None:
        raise HTTPException(404, "Processo não encontrado.")
    dia = hoje()
    todas = mensagens(proc, dia)
    titular = proc.campos.get("titular")
    uc = proc.campos.get("uc")
    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "p": proc,
            "titular": str(titular.valor).title() if titular and titular.valor else "—",
            "uc": uc.valor if uc and uc.valor else "—",
            "integrador": [m for m in todas if m.canal == "integrador"],
            "cliente": [m for m in todas if m.canal == "cliente"],
            "sugestoes": sugestoes(proc),
            "hoje": dia,
        },
    )
