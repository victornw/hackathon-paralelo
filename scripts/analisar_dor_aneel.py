"""Reproduz agregados de Enel CE no ZIP oficial, sem exportar identificadores."""

import argparse
import csv
import hashlib
import io
import json
import math
import statistics
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path


def data(value):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value[:19], fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Formato de data desconhecido: {value}")


def analisar(path):
    ultimos = {}
    linhas = enel = 0
    campos = [
        "DatSolicitacao",
        "DatInj",
        "DscSituacaoConexao",
        "DscStatusConexao",
        "DscMotivoSituacao",
        "DscSubgrupoTarifario",
        "MdaPotencia",
        "DatPrzEnvio",
    ]
    with zipfile.ZipFile(path) as z:
        arquivo = next(n for n in z.namelist() if n.endswith(".csv"))
        with z.open(arquivo) as f:
            reader = csv.DictReader(
                io.TextIOWrapper(f, encoding="utf-8-sig"), delimiter=";"
            )
            for row in reader:
                linhas += 1
                if row["SigAgenteDistribuicao"].strip() != "Enel CE":
                    continue
                enel += 1
                key = row["NumProtocolo"]
                envio = data(row["DatPrzEnvio"])
                if not key or envio is None:
                    raise ValueError(
                        "Não é possível deduplicar sem protocolo/data de envio"
                    )
                anterior = ultimos.get(key)
                if anterior is None or envio >= anterior[0]:
                    ultimos[key] = (envio, {c: row[c] for c in campos})
    todos = [v[1] for v in ultimos.values()]
    residencial = [
        r
        for r in todos
        if r["DscSubgrupoTarifario"].strip().upper() == "B1"
        and 0 < float(r["MdaPotencia"].replace(",", ".")) <= 10
    ]

    def resumo(rows):
        intervalos = []
        negativas = ausentes = 0
        for r in rows:
            a, b = data(r["DatSolicitacao"]), data(r["DatInj"])
            if a is None or b is None:
                ausentes += 1
            elif (b - a).days < 0:
                negativas += 1
            else:
                intervalos.append((b - a).days)
        intervalos.sort()
        return {
            "pedidos": len(rows),
            "status": dict(Counter(r["DscStatusConexao"] for r in rows)),
            "situacoes": dict(Counter(r["DscSituacaoConexao"] for r in rows)),
            "motivos": dict(Counter(r["DscMotivoSituacao"] for r in rows)),
            "solicitacao_ate_injecao": {
                "n_datas_validas": len(intervalos),
                "datas_ausentes": ausentes,
                "intervalos_negativos_excluidos": negativas,
                "mediana_dias_corridos": statistics.median(intervalos)
                if intervalos
                else None,
                "p90_dias_corridos_nearest_rank": intervalos[
                    math.ceil(0.9 * len(intervalos)) - 1
                ]
                if intervalos
                else None,
            },
        }

    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "fonte": "https://dadosabertos.aneel.gov.br/dataset/atendimento-mmgd-mini-e-micro-geracao-distribuida",
        "sha256_zip": digest.hexdigest(),
        "linhas_nordeste": linhas,
        "linhas_enel_ce_antes_dedup": enel,
        "metodo": "Filtrar Enel CE; deduplicar por NumProtocolo, mantendo maior DatPrzEnvio; empate mantém última linha do arquivo. Residencial: B1 e 0 < MdaPotencia <= 10. Sem recorte de data adicional.",
        "periodo_solicitacoes": {
            "inicio": str(
                min(
                    data(r["DatSolicitacao"])
                    for r in todos
                    if data(r["DatSolicitacao"])
                )
            ),
            "fim": str(
                max(
                    data(r["DatSolicitacao"])
                    for r in todos
                    if data(r["DatSolicitacao"])
                )
            ),
        },
        "enel_ce_todos_segmentos": resumo(todos),
        "enel_ce_b1_ate10kw": resumo(residencial),
        "limites": "Base histórica observacional; não mede horas de engenharia, causas individuais ou economia do nosso agente. Datas faltantes/casos ainda não conectados não entram na mediana. Motivos não foram interpretados como causa sem validação do preenchimento.",
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("zip", type=Path)
    ap.add_argument("--saida", type=Path, required=True)
    args = ap.parse_args()
    result = analisar(args.zip)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(args.saida)
    for grupo in ["enel_ce_todos_segmentos", "enel_ce_b1_ate10kw"]:
        print(grupo, result[grupo]["pedidos"], result[grupo]["solicitacao_ate_injecao"])
