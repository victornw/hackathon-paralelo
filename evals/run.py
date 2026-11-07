"""Slide de números: uma tabela só, com valores medidos ou "não medido".

Uso: .venv/bin/python -m evals.run [--db PATH] [--aneel PATH] [--saida evals/resultados.md]

Regra: nenhum número é inventado ou estimado. Sem dado, a linha diz "não medido".
O banco de --db é aberto só para leitura; classificador e relógio simulado usam
um banco temporário.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.schemas import PassoTrace

CABECALHO = "| Métrica | Valor | Base | Observação |\n|---|---|---|---|"
MIN_EXECUCOES = 5
NAO_MEDIDO = "não medido"


def pct(x: float) -> str:
    return f"{x * 100:.1f}%".replace(".", ",")


def num(x: float, casas: int = 1) -> str:
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def brl(x: float) -> str:
    return f"R$ {num(x, 2)}"


def _linha(metrica: str, valor: str, base: str, obs: str) -> dict:
    return {"metrica": metrica, "valor": valor, "base": base, "obs": obs}


@contextmanager
def _db_temporario() -> Iterator[None]:
    """DB_PATH temporário durante o bloco; restaura o valor anterior ao sair."""
    anterior = os.environ.get("DB_PATH")
    with tempfile.TemporaryDirectory(prefix="eval_run_") as pasta:
        os.environ["DB_PATH"] = str(Path(pasta) / "eval.db")
        try:
            yield
        finally:
            if anterior is None:
                os.environ.pop("DB_PATH", None)
            else:
                os.environ["DB_PATH"] = anterior


# --- 1. Classificador de pendências -----------------------------------------


def secao_pendencias() -> list[dict]:
    from evals import pendencias as ev

    with _db_temporario():
        resultados, llm_ok = ev.executar()
    produto = next(
        r for nome, r in resultados.items() if nome.startswith("Classificador")
    )
    palavras = resultados["Linha de base: palavras-chave"]
    majoritaria = next(
        r for nome, r in resultados.items() if nome.startswith("Classe maj")
    )
    llm = (
        "LLM configurado"
        if llm_ok
        else "LLM não configurado (classificador = palavras-chave)"
    )
    obs = f"textos sintéticos, rotulados antes de rodar o modelo; {llm}"
    n = produto["n"]
    npar = produto["n_parafrase"]
    base = f"{n} textos"
    return [
        _linha(
            "Pendências: acerto geral (produto)",
            pct(produto["acerto_geral"]),
            base,
            obs,
        ),
        _linha(
            "Pendências: acerto em paráfrases (produto)",
            pct(produto["acerto_parafrase"]),
            f"{npar} paráfrases",
            obs,
        ),
        _linha(
            "Pendências: acerto geral (palavras-chave)",
            pct(palavras["acerto_geral"]),
            base,
            "linha de base",
        ),
        _linha(
            "Pendências: acerto em paráfrases (palavras-chave)",
            pct(palavras["acerto_parafrase"]),
            f"{npar} paráfrases",
            "linha de base",
        ),
        _linha(
            "Pendências: acerto geral (classe majoritária)",
            pct(majoritaria["acerto_geral"]),
            base,
            "linha de base; dados balanceados",
        ),
    ]


# --- 2. Custo e latência -----------------------------------------------------


def _passos_por_processo(db: str | Path) -> dict[str, list[PassoTrace]]:
    caminho = Path(db)
    if not caminho.is_file():
        return {}
    con = sqlite3.connect(f"file:{caminho.resolve()}?mode=ro", uri=True)
    try:
        try:
            linhas = con.execute(
                "SELECT processo_id, json FROM passos_trace ORDER BY id"
            ).fetchall()
        except sqlite3.OperationalError:  # banco sem a tabela de trace
            return {}
    finally:
        con.close()
    por_processo: dict[str, list[PassoTrace]] = {}
    for processo_id, js in linhas:
        if processo_id == "sem_processo" or processo_id.startswith("demo-"):
            continue
        por_processo.setdefault(processo_id, []).append(
            PassoTrace.model_validate_json(js)
        )
    return por_processo


def secao_custo(db: str | Path) -> list[dict]:
    reais = {
        pid: passos
        for pid, passos in _passos_por_processo(db).items()
        if any(p.tokens_entrada + p.tokens_saida > 0 for p in passos)
    }
    n = len(reais)
    if n == 0:
        return [
            _linha(
                "Custo por processo",
                NAO_MEDIDO,
                "—",
                "nenhuma execução com LLM no trace",
            )
        ]
    todos = [p for passos in reais.values() for p in passos]
    tokens = sum(p.tokens_entrada + p.tokens_saida for p in todos) / n
    segundos = sum(p.ms for p in todos) / n / 1000
    custo = sum(p.custo_brl for p in todos) / n
    com_erro = sum(1 for p in todos if p.erro)
    base = f"{n} processo{'s' if n != 1 else ''} com LLM"
    obs = "médias por processo completo"
    if n < MIN_EXECUCOES:
        obs += f"; abaixo das {MIN_EXECUCOES} execuções previstas"
    return [
        _linha("Tokens por processo (média)", num(tokens, 0), base, obs),
        _linha("Tempo por processo (média)", f"{num(segundos)} s", base, obs),
        _linha("Custo por processo (média)", brl(custo), base, obs),
        _linha(
            "Passos com erro",
            pct(com_erro / len(todos)),
            f"{len(todos)} passos",
            f"{com_erro} de {len(todos)} passos",
        ),
    ]


# --- 3. Cobertura ANEEL ------------------------------------------------------


def cobertura_aneel(caminho: str | Path) -> list[dict]:
    """Cobertura das categorias de pendência frente à base ANEEL (colunas ainda desconhecidas)."""
    raise NotImplementedError("leitor da base ANEEL ainda não implementado")


def secao_aneel(caminho: str | Path | None) -> list[dict]:
    metrica = "Cobertura das categorias ANEEL"
    if not caminho or not Path(caminho).is_file():
        return [_linha(metrica, NAO_MEDIDO, "—", "base ANEEL não encontrada")]
    try:
        return cobertura_aneel(caminho)
    except NotImplementedError:
        return [
            _linha(
                metrica, NAO_MEDIDO, "—", "leitor da base ANEEL ainda não implementado"
            )
        ]


# --- Saída -------------------------------------------------------------------


def _data_hoje() -> str:
    from app.portal_sim.relogio import hoje

    with _db_temporario():
        return hoje().strftime("%d/%m/%Y")


def montar(db: str | Path, aneel: str | Path | None) -> str:
    linhas = secao_pendencias() + secao_custo(db) + secao_aneel(aneel)
    corpo = [
        f"| {r['metrica']} | {r['valor']} | {r['base']} | {r['obs']} |" for r in linhas
    ]
    rodape = (
        f"Gerado em {_data_hoje()} com dados sintéticos; "
        "números marcados 'não medido' não entram no pitch."
    )
    return "\n".join([CABECALHO, *corpo, "", rodape]) + "\n"


def main(argv: list[str] | None = None) -> str:
    ap = argparse.ArgumentParser(description="Gera o slide de números (markdown).")
    ap.add_argument("--db", default=os.environ.get("DB_PATH", "data/app.db"))
    ap.add_argument("--aneel", default=None)
    ap.add_argument("--saida", default=str(Path(__file__).parent / "resultados.md"))
    args = ap.parse_args(argv)
    texto = montar(args.db, args.aneel)
    print(texto, end="")
    Path(args.saida).write_text(texto, encoding="utf-8")
    return texto


if __name__ == "__main__":
    main()
