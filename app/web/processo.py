"""Telas do integrador: novo processo e detalhe do processo."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core import orquestrador, repositorio
from app.portal_sim.relogio import hoje
from app.schemas import Etapa, Processo
from app.web.painel import ROTULOS, contexto_documentos

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
router = APIRouter()

RAIZ = Path(__file__).resolve().parents[2]
EMAIL_EXEMPLO = "integrador.exemplo@exemplo.com"

ROTULOS_CAMPOS = {
    "uc": "Código da UC",
    "titular": "Titular",
    "cpf_cnpj": "CPF/CNPJ",
    "endereco": "Endereço",
    "cidade": "Cidade",
    "classe": "Classe",
    "subgrupo": "Subgrupo",
    "tipo_ligacao": "Tipo de ligação",
    "tensao_atendimento_v": "Tensão de atendimento (V)",
    "consumo_medio_kwh": "Consumo médio (kWh)",
}
STATUS_REGRA = {
    "aprovada": ("aprovada", "ok"),
    "reprovada": ("reprovada", "vencido"),
    "incerta": ("incerta", "atencao"),
    "nao_verificada": ("não verificada", "neutro"),
}
LIMITE_CONFIANCA = 0.8


def _numero(v: float) -> str:
    return f"{v:g}".replace(".", ",")


def _linhas_campos(p: Processo) -> list[dict]:
    linhas = []
    for chave, c in p.campos.items():
        vazio = c.valor is None or str(c.valor).strip() == ""
        linhas.append(
            {
                "rotulo": ROTULOS_CAMPOS.get(chave, chave),
                "valor": "—" if vazio else str(c.valor),
                "pct": round(c.confianca * 100),
                "incerto": vazio or c.confianca < LIMITE_CONFIANCA,
                "trecho": c.fonte.trecho if c.fonte and c.fonte.trecho else "",
            }
        )
    return linhas


def _contexto(p: Processo) -> dict:
    titular = p.campos.get("titular")
    uc = p.campos.get("uc")
    abertas = [
        q
        for q in p.perguntas
        if q.destinatario == "integrador"
        and not q.resposta
        and not q.id.startswith("falha:")
    ]
    falhas = [q for q in p.perguntas if q.id.startswith("falha:") and not q.resposta]
    respondidas = [q for q in p.perguntas if q.resposta]
    trabalhando = not abertas and not falhas and orquestrador.trabalhando(p)
    regras = []
    for r in p.regras:
        rotulo, cor = STATUS_REGRA.get(r.status.value, (r.status.value, "neutro"))
        regras.append({"r": r, "rotulo": rotulo, "cor": cor})
    kit = p.kit
    return {
        "p": p,
        "hoje": hoje(),
        "titular": str(titular.valor).title()
        if titular and titular.valor
        else "Processo novo",
        "uc": uc.valor if uc and uc.valor else "—",
        "etapa_rotulo": ROTULOS[p.etapa],
        "em_revisao": p.etapa in (Etapa.EM_REVISAO, Etapa.PENDENCIA)
        and not p.revisado_por
        and not trabalhando,
        "trabalhando": trabalhando,
        "linhas": _linhas_campos(p),
        "kit": kit,
        "kwp": _numero(kit.potencia_total_wp / 1000) if kit else None,
        "abertas": abertas,
        "falhas": falhas,
        "respondidas": respondidas,
        "regras": regras,
        **contexto_documentos(p),
    }


@router.get("/processos/novo")
def novo(request: Request):
    return templates.TemplateResponse(request, "processo_novo.html", {"hoje": hoje()})


@router.post("/processos/novo/exemplo/{n}")
def novo_exemplo(n: int, tarefas: BackgroundTasks):
    if n not in (1, 2, 3):
        raise HTTPException(404, "Exemplo não encontrado.")
    pasta = RAIZ / "fixtures" / "contas"
    p = repositorio.criar(email_contato=EMAIL_EXEMPLO)
    for tipo, sufixo in (("conta", "conta"), ("proposta", "proposta")):
        arq = pasta / f"cliente_{n}_{sufixo}.pdf"
        repositorio.guardar_arquivo(p.id, tipo, arq.name, arq.read_bytes())
    tarefas.add_task(orquestrador.orquestrar, p.id)
    return RedirectResponse(f"/processos/{p.id}", status_code=303)


@router.get("/processos/{processo_id}")
def detalhe(request: Request, processo_id: str, tarefas: BackgroundTasks):
    try:
        p = repositorio.carregar(processo_id)
    except repositorio.ProcessoNaoEncontrado:
        return templates.TemplateResponse(
            request,
            "processo_detalhe.html",
            {"hoje": hoje(), "p": None, "titular": "Processo não encontrado"},
            status_code=404,
        )
    ctx = _contexto(p)
    if ctx["trabalhando"]:
        # Há passo a rodar e talvez ninguém rodando (ex.: caso recriado na partida).
        tarefas.add_task(orquestrador.orquestrar, p.id)
    return templates.TemplateResponse(request, "processo_detalhe.html", ctx)
