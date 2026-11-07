"""Eval do classificador de pendências contra linhas de base.

Os textos são sintéticos, rotulados à mão antes de rodar qualquer modelo.
Uso: .venv/bin/python -m evals.pendencias
"""

from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from app.portal_sim.pendencias import CATEGORIAS, classificar_por_palavras

CAMINHO_PADRAO = Path(__file__).parent / "dados" / "pendencias_rotuladas.jsonl"


def carregar(caminho: str | Path = CAMINHO_PADRAO) -> list[dict]:
    dados: list[dict] = []
    ids: set[str] = set()
    with open(caminho, encoding="utf-8") as f:
        for n, linha in enumerate(f, 1):
            if not linha.strip():
                continue
            item = json.loads(linha)
            if item.get("id") in ids:
                raise ValueError(f"id duplicado: {item.get('id')} (linha {n})")
            ids.add(item.get("id"))
            if item.get("categoria") not in CATEGORIAS:
                raise ValueError(f"categoria inválida em {item.get('id')}")
            if not str(item.get("texto", "")).strip():
                raise ValueError(f"texto vazio em {item.get('id')}")
            item.setdefault("parafrase", False)
            dados.append(item)
    return dados


def _acerto(itens: list[dict], previsoes: dict[str, str]) -> float:
    if not itens:
        return 0.0
    return sum(previsoes[i["id"]] == i["categoria"] for i in itens) / len(itens)


def avaliar(classificar: Callable[[str], str], dados: list[dict]) -> dict:
    previsoes = {d["id"]: classificar(d["texto"]) for d in dados}
    por_categoria = {
        cat: _acerto([d for d in dados if d["categoria"] == cat], previsoes)
        for cat in CATEGORIAS
        if any(d["categoria"] == cat for d in dados)
    }
    parafrases = [d for d in dados if d.get("parafrase")]
    erros = [
        {"id": d["id"], "esperado": d["categoria"], "obtido": previsoes[d["id"]]}
        for d in dados
        if previsoes[d["id"]] != d["categoria"]
    ]
    return {
        "n": len(dados),
        "acerto_geral": _acerto(dados, previsoes),
        "acerto_por_categoria": por_categoria,
        "n_parafrase": len(parafrases),
        "acerto_parafrase": _acerto(parafrases, previsoes),
        "erros": erros,
    }


def classe_majoritaria(dados: list[dict]) -> str:
    return Counter(d["categoria"] for d in dados).most_common(1)[0][0]


def _produto() -> Callable[[str], str]:
    """Classificador do produto; DB_PATH temporário para não escrever no banco do app."""
    if "DB_PATH" not in os.environ:
        os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp(prefix="eval_")) / "eval.db")
    from app.portal_sim.pendencias import classificar_pendencia

    return lambda t: classificar_pendencia(t)[0]


def tabela_markdown(resultados: dict[str, dict]) -> str:
    linhas = [
        "| Método | Acerto geral | Acerto em paráfrases | n |",
        "|---|---|---|---|",
    ]
    for nome, r in resultados.items():
        linhas.append(
            f"| {nome} | {r['acerto_geral']:.1%} | {r['acerto_parafrase']:.1%} | {r['n']} |"
        )
    return "\n".join(linhas)


def _llm_disponivel() -> bool:
    from app.core import llm

    return llm.disponivel("pendencia")


def executar(dados: list[dict] | None = None) -> tuple[dict[str, dict], bool]:
    dados = dados if dados is not None else carregar()
    llm_ok = _llm_disponivel()
    majoritaria = classe_majoritaria(dados)
    produto = "Classificador do produto" + (
        "" if llm_ok else " (LLM não configurado: classificador = palavras-chave)"
    )
    resultados = {
        f"Classe majoritária ({majoritaria}; dados balanceados)": avaliar(
            lambda _t: majoritaria, dados
        ),
        "Linha de base: palavras-chave": avaliar(classificar_por_palavras, dados),
        produto: avaliar(_produto(), dados),
    }
    return resultados, llm_ok


if __name__ == "__main__":
    resultados, llm_ok = executar()
    print(tabela_markdown(resultados))
    print()
    print(
        "LLM disponível: sim."
        if llm_ok
        else "LLM não configurado: classificador = palavras-chave."
    )
    print("Textos sintéticos, rotulados antes de rodar qualquer modelo.")
    print("\nErros do classificador do produto:")
    produto = list(resultados.values())[-1]
    for e in produto["erros"]:
        print(f"- {e['id']}: esperado {e['esperado']}, obtido {e['obtido']}")
    if not produto["erros"]:
        print("- nenhum")
