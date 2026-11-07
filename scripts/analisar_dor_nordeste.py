"""Agrega pedidos ANEEL por distribuidora, com último envio por protocolo."""

import argparse
import csv
import hashlib
import io
import json
import zipfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


def analisar(path):
    ultimos = {}
    linhas = sem_chave = 0
    geracoes = Counter()
    with (
        zipfile.ZipFile(path) as z,
        z.open(next(n for n in z.namelist() if n.endswith(".csv"))) as f,
    ):
        for row in csv.DictReader(
            io.TextIOWrapper(f, encoding="utf-8-sig"), delimiter=";"
        ):
            linhas += 1
            geracoes[row["DatGeracaoConjuntoDados"]] += 1
            agente, protocolo = (
                row["SigAgenteDistribuicao"].strip(),
                row["NumProtocolo"].strip(),
            )
            envio = row["DatPrzEnvio"].strip()
            if not agente or not protocolo or not envio:
                sem_chave += 1
                continue
            envio = date.fromisoformat(envio[:10])
            key = (agente, protocolo)
            anterior = ultimos.get(key)
            if anterior is None or envio >= anterior[0]:
                ultimos[key] = (
                    envio,
                    row["DscSubgrupoTarifario"].strip(),
                    float(row["MdaPotencia"].replace(",", "."))
                    if row["MdaPotencia"].strip()
                    else None,
                    row["DscStatusConexao"].strip(),
                    row["DscSituacaoConexao"].strip(),
                    row["DscMotivoSituacao"].strip(),
                    row["NomUF"],
                    row["DatSolicitacao"][:10],
                    row["DscFonteGeracao"].strip(),
                )
    agregados = defaultdict(
        lambda: {
            "todos": Counter(),
            "b1_ate10kw": Counter(),
            "b1_solar_ate10kw": Counter(),
            "ufs": set(),
            "motivos_negados": Counter(),
            "solicitacoes": set(),
            "envios": set(),
            "fontes": Counter(),
        }
    )
    for (agente, _), (
        envio,
        subgrupo,
        potencia,
        status,
        situacao,
        motivo,
        uf,
        solicitacao,
        fonte,
    ) in ultimos.items():
        g = agregados[agente]
        g["ufs"].add(uf)
        if solicitacao:
            g["solicitacoes"].add(solicitacao)
        g["envios"].add(envio.isoformat())
        g["fontes"][fonte] += 1
        grupos = [g["todos"]]
        if subgrupo.upper() == "B1" and potencia is not None and 0 < potencia <= 10:
            grupos.append(g["b1_ate10kw"])
            if fonte.upper() == "UFV" and "2022-01-07" <= solicitacao <= "2023-01-07":
                grupos.append(g["b1_solar_ate10kw"])
        negado = "negad" in status.casefold()
        if negado:
            g["motivos_negados"][motivo] += 1
        for c in grupos:
            c["pedidos"] += 1
            if negado:
                c["negados"] += 1
            if (
                negado
                and "documenta" in motivo.casefold()
                and "incompleta" in motivo.casefold()
            ):
                c["negados_documentacao_incompleta"] += 1
            if "perdeu validade" in situacao.casefold():
                c["orcamentos_perderam_validade"] += 1
    out = []
    for agente, g in agregados.items():
        out.append(
            {
                "agente": agente,
                "ufs": sorted(g["ufs"]),
                "solicitacao_min": min(g["solicitacoes"], default=None),
                "solicitacao_max": max(g["solicitacoes"], default=None),
                "envio_min": min(g["envios"], default=None),
                "envio_max": max(g["envios"], default=None),
                **{
                    k: dict(v)
                    for k, v in g.items()
                    if k not in {"ufs", "solicitacoes", "envios"}
                },
            }
        )
    with Path(path).open("rb") as f:
        sha = hashlib.file_digest(f, "sha256").hexdigest()
    return {
        "fonte": "https://dadosabertos.aneel.gov.br/dataset/atendimento-mmgd-mini-e-micro-geracao-distribuida",
        "linhas": linhas,
        "linhas_sem_chave_ou_envio_excluidas": sem_chave,
        "geracoes_dataset": dict(geracoes),
        "coorte_b1_solar_ate10kw": "B1; 0 < MdaPotencia <= 10; DscFonteGeracao = UFV; DatSolicitacao entre 2022-01-07 e 2023-01-07, inclusivos.",
        "sha256_zip": sha,
        "metodo": "Última DatPrzEnvio por (distribuidora, protocolo), empate mantém última linha. Documentação incompleta contada apenas quando status é pedido negado e motivo o declara. B1 até 10 kW é recorte residencial. Campos pessoais não são exportados.",
        "distribuidoras": sorted(
            out,
            key=lambda x: x["todos"].get("negados_documentacao_incompleta", 0),
            reverse=True,
        ),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("zip", type=Path)
    p.add_argument("--saida", type=Path, required=True)
    args = p.parse_args()
    result = analisar(args.zip)
    args.saida.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    for d in result["distribuidoras"]:
        print(d["agente"], d["ufs"], d["todos"], d["b1_ate10kw"], flush=True)
