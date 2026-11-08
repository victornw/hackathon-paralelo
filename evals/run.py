"""Slide de números: uma tabela só, com valores medidos ou "não medido".

Uso: .venv/bin/python -m evals.run [--db PATH] [--aneel PATH] [--saida evals/resultados.md]
(--aneel aceita um arquivo da base ou a pasta com os ZIPs das cinco regiões)

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
from typing import Literal

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


Cobertura = Literal["coberto", "nao_coberto"]

COBERTURA: dict[str, Cobertura] = {
    "Documentação incompleta": "coberto",
    "Documentação incorreta": "coberto",
    "Não aprovação nos prazos estabelecidos (art. 83, § 7º, I)": "coberto",
    "Não devolução dos contratos assinados no prazo (art. 83, § 7º, III)": "coberto",
    "Vistoria não solicitada": "coberto",
    "Vistoria reprovada, aguardando nova solicitação": "nao_coberto",
}
RAZAO: dict[str, str] = {
    "Documentação incompleta": "o agente pede o que falta antes de protocolar",
    "Documentação incorreta": "o agente confere contra a norma antes de protocolar",
    "Não aprovação nos prazos estabelecidos (art. 83, § 7º, I)": "prazos do integrador vigiados",
    "Não devolução dos contratos assinados no prazo (art. 83, § 7º, III)": "prazos do integrador vigiados",
    "Vistoria não solicitada": "o agente lembra de solicitar a vistoria",
    "Vistoria reprovada, aguardando nova solicitação": "problema físico da instalação",
}
SITUACOES_VISTORIA = (
    "Vistoria não solicitada",
    "Vistoria reprovada, aguardando nova solicitação",
)
STATUS_NEGADO = "Pedidos Negados"
ENEL_CE = "Enel CE"
COLUNAS_ANEEL = (
    "SigAgenteDistribuicao",
    "NumProtocolo",
    "DatPrzEnvio",
    "DatSolicitacao",
    "MdaPotencia",
    "DscSubgrupoTarifario",
    "DscFonteGeracao",
    "DscStatusConexao",
    "DscMotivoSituacao",
    "DscSituacaoConexao",
)
OBS_ANEEL = (
    "ANEEL 2022–2023, B1 solar até 10 kW; categorias registradas pela distribuidora; "
    "não mede pendências corrigidas antes da negativa"
)


def _ler_aneel(caminho: Path):
    """Lê só as colunas usadas; devolve (DataFrame, colunas ausentes).

    `caminho` pode ser um arquivo (parquet, ZIP ou CSV) ou uma pasta com os ZIPs
    das cinco regiões; na pasta, cada arquivo é lido em blocos e já deduplicado,
    porque o CSV do Sudeste tem vários gigabytes."""
    import pandas as pd

    if caminho.is_dir():
        arquivos = sorted(caminho.glob("*.zip")) or sorted(caminho.glob("*.parquet"))
        partes = []
        for arq in arquivos:
            if arq.suffix == ".parquet":
                partes.append(_ler_aneel(arq)[0])
                continue
            for bloco in pd.read_csv(
                arq,
                sep=";",
                encoding="utf-8-sig",
                dtype=str,
                usecols=lambda c: c in COLUNAS_ANEEL,
                compression="zip",
                chunksize=2_000_000,
            ):
                if {"DatPrzEnvio", "SigAgenteDistribuicao", "NumProtocolo"} <= set(
                    bloco.columns
                ):
                    bloco = bloco.sort_values(
                        "DatPrzEnvio", kind="stable"
                    ).drop_duplicates(
                        ["SigAgenteDistribuicao", "NumProtocolo"], keep="last"
                    )
                partes.append(bloco)
        df = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
        return df, [c for c in COLUNAS_ANEEL if c not in df.columns]

    if caminho.suffix == ".parquet":
        import pyarrow.parquet as pq

        presentes = [
            c for c in COLUNAS_ANEEL if c in pq.ParquetFile(caminho).schema_arrow.names
        ]
        df = pd.read_parquet(caminho, columns=presentes)
    else:  # ZIP ou CSV do portal de dados abertos (separador ";", decimal ",")
        df = pd.read_csv(
            caminho,
            sep=";",
            encoding="utf-8-sig",
            dtype=str,
            usecols=lambda c: c in COLUNAS_ANEEL,
            compression="zip" if caminho.suffix == ".zip" else None,
        )
    return df, [c for c in COLUNAS_ANEEL if c not in df.columns]


def coorte_aneel(df):
    """Mesma coorte e dedup de scripts/analisar_dor_nordeste.py e
    scripts/aneel/recontagem_coorte.py: último DatPrzEnvio por (distribuidora,
    protocolo), empate fica com a última linha; linhas sem chave ou sem envio caem."""
    import pandas as pd

    df = df.assign(
        SigAgenteDistribuicao=df.SigAgenteDistribuicao.astype(str).str.strip(),
        NumProtocolo=df.NumProtocolo.astype(str).str.strip(),
        DatPrzEnvio=pd.to_datetime(df.DatPrzEnvio, errors="coerce"),
        DatSolicitacao=pd.to_datetime(df.DatSolicitacao, errors="coerce"),
        MdaPotencia=pd.to_numeric(
            df.MdaPotencia.astype(str).str.replace(",", ".", regex=False),
            errors="coerce",
        ),
    )
    df = df[
        df.DatPrzEnvio.notna()
        & (df.SigAgenteDistribuicao != "")
        & (df.NumProtocolo != "")
    ]
    df = df.sort_values("DatPrzEnvio", kind="stable").drop_duplicates(
        ["SigAgenteDistribuicao", "NumProtocolo"], keep="last"
    )
    return df[
        (df.DscSubgrupoTarifario.str.strip() == "B1")
        & (df.MdaPotencia > 0)
        & (df.MdaPotencia <= 10)
        & (df.DscFonteGeracao.str.strip() == "UFV")
        & (df.DatSolicitacao >= "2022-01-07")
        & (df.DatSolicitacao <= "2023-01-07")
    ]


def _categorias_problema(coorte):
    """Categoria de cada caso-problema: motivo se negado, senão a situação de vistoria."""
    negado = coorte.DscStatusConexao.str.strip() == STATUS_NEGADO
    vistoria = coorte.DscSituacaoConexao.str.strip().isin(SITUACOES_VISTORIA)
    motivo = (
        coorte.DscMotivoSituacao.fillna("")
        .str.strip()
        .replace("", "Sem motivo registrado")
    )
    categoria = motivo.where(negado, coorte.DscSituacaoConexao.str.strip())
    return categoria[negado | vistoria]


def _linhas_escopo(nome: str, coorte) -> list[dict]:
    casos = _categorias_problema(coorte).value_counts()
    base = f"{nome}: {len(coorte)} pedidos da coorte"
    if casos.empty:
        return [_linha(f"ANEEL {nome}: casos-problema", "0", base, OBS_ANEEL)]
    cobertos = casos[[COBERTURA.get(c) == "coberto" for c in casos.index]]
    total = int(casos.sum())
    linhas = [
        _linha(
            f"ANEEL {nome}: casos-problema (negados + vistoria parada)",
            num(total, 0),
            base,
            OBS_ANEEL,
        ),
        _linha(
            f"ANEEL {nome}: casos-problema em categorias cobertas",
            pct(cobertos.sum() / total),
            f"{num(int(cobertos.sum()), 0)} de {num(total, 0)} casos-problema",
            OBS_ANEEL,
        ),
    ]
    for categoria, n in cobertos.head(2).items():
        linhas.append(
            _linha(
                f"ANEEL {nome}: {categoria}",
                num(int(n), 0),
                f"{num(total, 0)} casos-problema",
                f"coberto: {RAZAO[categoria]}; {OBS_ANEEL}",
            )
        )
    return linhas


def cobertura_aneel(caminho: str | Path) -> list[dict]:
    """Linhas do slide: casos-problema e % coberto pelo agente, Enel CE e Nordeste."""
    df, ausentes = _ler_aneel(Path(caminho))
    if ausentes:
        return [
            _linha(
                "Cobertura das categorias ANEEL",
                NAO_MEDIDO,
                "—",
                f"colunas ausentes na base: {', '.join(ausentes)}",
            )
        ]
    coorte = coorte_aneel(df)
    if Path(caminho).is_dir():
        # Base completa (cinco regiões): o país e as distribuidoras citadas no pitch.
        linhas = _linhas_escopo("Brasil", coorte)
        for dist in ("Cemig-D", "Equatorial AL", ENEL_CE):
            linhas += _linhas_escopo(dist, coorte[coorte.SigAgenteDistribuicao == dist])
        return linhas
    return _linhas_escopo(
        "Enel CE", coorte[coorte.SigAgenteDistribuicao == ENEL_CE]
    ) + _linhas_escopo("Nordeste", coorte)


def secao_aneel(caminho: str | Path | None) -> list[dict]:
    metrica = "Cobertura das categorias ANEEL"
    if not caminho or not Path(caminho).exists():
        return [_linha(metrica, NAO_MEDIDO, "—", "base ANEEL não encontrada")]
    return cobertura_aneel(caminho)


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
