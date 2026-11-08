"""GET /metricas: o que o agente fez na carteira e o que os evals mediram.

Dois tipos de número, sempre rotulados: os da carteira ao vivo (processos,
regras, prazos, perguntas, revisões gravadas no tracing) e os dos evals já
rodados com IA real (lidos de evals/resultados_*.md). Um número que não existe
ainda aparece como "sem medição", nunca inventado.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.portal_sim.prazos import calcular_prazos
from app.portal_sim.relogio import hoje
from app.schemas import Etapa
from app.web.painel import ROTULOS, PrazoTela, carregar_processos

RAIZ = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
router = APIRouter()


def _br(v: float, casas: int = 1) -> str:
    return f"{v:.{casas}f}".replace(".", ",")


def eval_processo_completo(texto: str) -> dict | None:
    m = re.search(
        r"Médias de (\d+) execução\(ões\), (\d+) concluída\(s\): ([\d.]+) chamadas LLM, "
        r"(\d+) tokens in, (\d+) tokens out, ([\d.]+) s de LLM, ([\d.]+) s de relógio",
        texto,
    )
    if not m:
        return None
    execucoes, concluidas, chamadas, tin, tout, _, relogio = m.groups()
    return {
        "execucoes": int(execucoes),
        "concluidas": int(concluidas),
        "chamadas": _br(float(chamadas), 0),
        "tokens": _br((int(tin) + int(tout)) / 1000),
        "segundos": _br(float(relogio)),
    }


def eval_pendencias(texto: str) -> dict | None:
    produto = re.search(r"\| Classificador do produto \| ([\d.]+)% \| ([\d.]+)% \| (\d+) \|", texto)
    base = re.search(r"\| Linha de base: palavras-chave \| ([\d.]+)% \|", texto)
    if not produto:
        return None
    return {
        "acerto": _br(float(produto.group(1))),
        "parafrases": _br(float(produto.group(2))),
        "n": int(produto.group(3)),
        "base": _br(float(base.group(1))) if base else None,
    }


def _ler(nome: str) -> str:
    try:
        return (RAIZ / "evals" / nome).read_text()
    except OSError:
        return ""


def contexto(dia) -> dict:
    from app.tracing import listar_passos
    from app.web.revisao import PASSO as PASSO_REVISAO

    processos = carregar_processos()
    ativos = [p for p in processos if p.etapa != Etapa.CONCLUIDO]

    pegas = Counter()
    descricoes = {}
    for p in processos:
        for r in p.regras:
            if r.status.value in ("reprovada", "incerta"):
                pegas[r.regra_id] += 1
                descricoes[r.regra_id] = r.descricao

    prazos = [PrazoTela.de(pr, dia) for p in ativos for pr in calcular_prazos(p)]
    situacoes = Counter(x.situacao for x in prazos)
    vencidos_enel = sum(
        1 for x in prazos if x.situacao == "vencido" and x.prazo.conta_contra == "distribuidora"
    )

    revisoes = [
        ps.ms / 60000
        for p in processos
        for ps in listar_passos(p.id)
        if ps.passo == PASSO_REVISAO
    ]
    perguntas = [q for p in processos for q in p.perguntas if not q.id.startswith("falha:")]

    return {
        "hoje": dia,
        "total": len(processos),
        "ativos": len(ativos),
        "etapas_ativas": len({p.etapa for p in ativos}),
        "pegas_total": sum(pegas.values()),
        "processos_com_pega": sum(
            1 for p in processos if any(r.status.value in ("reprovada", "incerta") for r in p.regras)
        ),
        "top_regras": [(rid, descricoes[rid], n) for rid, n in pegas.most_common(5)],
        "prazos": {
            "no_prazo": situacoes["no_prazo"],
            "risco": situacoes["atencao"] + situacoes["vence_hoje"],
            "vencidos": situacoes["vencido"],
            "vencidos_enel": vencidos_enel,
        },
        "por_etapa": Counter(ROTULOS[p.etapa] for p in ativos).most_common(),
        "perguntas_integrador": sum(1 for q in perguntas if q.destinatario == "integrador"),
        "perguntas_engenheiro": sum(1 for q in perguntas if q.destinatario == "engenheiro"),
        "respondidas": sum(1 for q in perguntas if q.resposta),
        "revisoes": len(revisoes),
        "revisao_media": _br(sum(revisoes) / len(revisoes)) if revisoes else None,
        "completo": eval_processo_completo(_ler("resultados_processo_completo.md")),
        "pendencias": eval_pendencias(_ler("resultados_pendencias.md")),
    }


@router.get("/metricas")
def metricas(request: Request):
    return templates.TemplateResponse(request, "metricas.html", contexto(hoje()))
