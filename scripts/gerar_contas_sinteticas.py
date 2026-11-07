"""Gera contas de luz e propostas sintéticas (PDF) com gabarito em JSON.

Imita o layout de uma conta da Enel Ceará para três clientes fictícios. Cada
cliente ganha `cliente_N_conta.pdf`, `cliente_N_proposta.pdf` (kit do catálogo
em app/core/catalogo.json) e `cliente_N_gabarito.json` com os valores e os
trechos literais esperados. Rode da raiz do repo:

    .venv/bin/python scripts/gerar_contas_sinteticas.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fpdf import FPDF

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "fixtures" / "contas"
CATALOGO = RAIZ / "app" / "core" / "catalogo.json"
CRIACAO = datetime(2026, 11, 1, tzinfo=UTC)
MARCA = "DOCUMENTO SINTÉTICO - DADOS FICTÍCIOS"

CLIENTES = [
    {
        "titular": "MARIA DAS GRAÇAS LIMA",
        "cpf_cnpj": "123.456.789-09",
        "endereco": "RUA DAS FLORES, 123 - ALDEOTA",
        "cidade": "FORTALEZA",
        "uc": "12345678",
        "tipo_ligacao": "MONOFÁSICO",
        "tensao": 220,
        "consumo": "412",
        "modulo": "HS-550M",
        "qtd_modulos": 10,
        "inversor": "SI-5000",
        "strings": [],
        "historico": [398, 405, 431, 389, 412, 420],
    },
    {
        "titular": "JOÃO PEDRO ALBUQUERQUE",
        "cpf_cnpj": "987.654.321-00",
        "endereco": "AV. DOM ALMEIDA LUSTOSA, 45 - CENTRO",
        "cidade": "CAUCAIA",
        "uc": "7654321",
        "tipo_ligacao": "BIFÁSICO",
        "tensao": 220,
        "consumo": "289,5",
        "modulo": "NF-600HC",
        "qtd_modulos": 4,
        "inversor": "MV-2000",
        "strings": [],
        "historico": [280, 301, 275, 296, 288, 290],
    },
    {
        "titular": "ANA BEATRIZ CAVALCANTE",
        "cpf_cnpj": "111.222.333-44",
        "endereco": "RUA DOS IPÊS, 800 - PRAIA DO FUTURO",
        "cidade": "EUSÉBIO",
        "uc": "23456789",
        "tipo_ligacao": "MONOFÁSICO",
        "tensao": 220,
        "consumo": "1.250",
        "modulo": "AE-610TB",
        "qtd_modulos": 14,
        "inversor": "SI-8000",
        "strings": [(1, 7), (2, 7)],
        "historico": [1190, 1302, 1255, 1240, 1288, 1225],
    },
]


def _novo_pdf(titulo: str) -> FPDF:
    pdf = FPDF()
    pdf.set_creation_date(CRIACAO)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, titulo, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(180, 0, 0)
    pdf.cell(0, 6, MARCA, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    return pdf


def _linhas(pdf: FPDF, linhas: list[str]) -> None:
    for linha in linhas:
        pdf.cell(0, 6, linha, new_x="LMARGIN", new_y="NEXT")


def gerar_conta(cliente: dict, caminho: Path) -> dict[str, str]:
    c = cliente
    trechos = {
        "titular": f"Nome: {c['titular']}",
        "cpf_cnpj": f"CPF: {c['cpf_cnpj']}",
        "endereco": f"Endereço: {c['endereco']}",
        "cidade": f"Cidade: {c['cidade']} - CE",
        "uc": f"Código da UC: {c['uc']}",
        "classe": "Classe: Residencial",
        "subgrupo": "Subgrupo: B1",
        "tipo_ligacao": f"Tipo de ligação: {c['tipo_ligacao']}",
        "tensao_atendimento_v": f"Tensão de atendimento: {c['tensao']} V",
        "consumo_medio_kwh": f"Consumo médio dos últimos 6 meses: {c['consumo']} kWh",
    }
    pdf = _novo_pdf("ENEL CEARÁ - CONTA DE ENERGIA ELÉTRICA")
    _linhas(pdf, ["Distribuidora: Companhia Energética (sintética) - Ceará", ""])
    _linhas(pdf, [trechos[k] for k in ("titular", "cpf_cnpj", "endereco", "cidade")])
    _linhas(pdf, ["", "DADOS DA UNIDADE CONSUMIDORA"])
    _linhas(
        pdf,
        [
            trechos[k]
            for k in (
                "uc",
                "classe",
                "subgrupo",
                "tipo_ligacao",
                "tensao_atendimento_v",
            )
        ],
    )
    _linhas(
        pdf,
        [
            "Modalidade tarifária: Convencional",
            "Vencimento: 10/11/2026",
            "Valor a pagar: R$ 387,90",
        ],
    )
    _linhas(pdf, ["", "HISTÓRICO DE CONSUMO (kWh)"])
    _linhas(pdf, [f"Mês -{i}: {kwh} kWh" for i, kwh in enumerate(c["historico"], 1)])
    _linhas(pdf, [trechos["consumo_medio_kwh"]])
    _linhas(pdf, ["", "Em caso de dúvidas, ligue 0800 000 0000 (número fictício)."])
    pdf.output(str(caminho))
    return trechos


def gerar_proposta(cliente: dict, catalogo: dict, caminho: Path) -> dict:
    c = cliente
    modulo = next(m for m in catalogo["modulos"] if m["modelo"] == c["modulo"])
    inversor = next(i for i in catalogo["inversores"] if i["modelo"] == c["inversor"])
    kwp = modulo["potencia_wp"] * c["qtd_modulos"] / 1000
    pdf = _novo_pdf("PROPOSTA COMERCIAL - SISTEMA FOTOVOLTAICO")
    _linhas(
        pdf, [f"Cliente: {c['titular']}", f"Local: {c['endereco']} - {c['cidade']}", ""]
    )
    _linhas(
        pdf,
        [
            "ESCOPO DO KIT",
            (
                f"Módulos fotovoltaicos: {c['qtd_modulos']} x {modulo['fabricante']} "
                f"{modulo['modelo']} - {modulo['potencia_wp']:.0f} Wp"
            ),
            (
                f"Inversor: 1 x {inversor['fabricante']} {inversor['modelo']} - "
                f"{inversor['potencia_nominal_w'] / 1000:.0f} kW"
            ),
            f"Potência instalada: {kwp:.2f} kWp".replace(".", ","),
        ],
    )
    for mppt, serie in c["strings"]:
        _linhas(
            pdf, [f"Configuração: MPPT {mppt} com 1 string de {serie} módulos em série"]
        )
    _linhas(
        pdf,
        [
            "",
            "Valor do investimento: R$ 21.900,00 (fictício)",
            "Prazo de instalação: 20 dias",
        ],
    )
    pdf.output(str(caminho))
    return {
        "modelo_modulo": modulo["modelo"],
        "qtd_modulos": c["qtd_modulos"],
        "modelo_inversor": inversor["modelo"],
        "strings": [{"mppt": m, "modulos_em_serie": s} for m, s in c["strings"]],
    }


def _valor_esperado(cliente: dict) -> dict:
    consumo = float(cliente["consumo"].replace(".", "").replace(",", "."))
    return {
        "uc": cliente["uc"],
        "titular": cliente["titular"],
        "cpf_cnpj": cliente["cpf_cnpj"],
        "endereco": cliente["endereco"],
        "cidade": cliente["cidade"],
        "classe": "Residencial",
        "subgrupo": "B1",
        "tipo_ligacao": {"MONOFÁSICO": "monofasico", "BIFÁSICO": "bifasico"}[
            cliente["tipo_ligacao"]
        ],
        "tensao_atendimento_v": cliente["tensao"],
        "consumo_medio_kwh": int(consumo) if consumo.is_integer() else consumo,
    }


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    for n, cliente in enumerate(CLIENTES, 1):
        trechos = gerar_conta(cliente, SAIDA / f"cliente_{n}_conta.pdf")
        kit = gerar_proposta(cliente, catalogo, SAIDA / f"cliente_{n}_proposta.pdf")
        valores = _valor_esperado(cliente)
        gabarito = {
            "campos": {k: {"valor": valores[k], "trecho": trechos[k]} for k in valores},
            "kit": kit,
        }
        (SAIDA / f"cliente_{n}_gabarito.json").write_text(
            json.dumps(gabarito, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"cliente {n}: ok")


if __name__ == "__main__":
    main()
