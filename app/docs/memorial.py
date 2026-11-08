"""Memorial descritivo em PDF (formato nosso: a Enel não fornece modelo até 10 kW)."""

from __future__ import annotations

from pathlib import Path

from app.docs.anexo_a import potencia_instalada_kw
from app.docs.pdf_base import (
    A_INFORMAR,
    DocPDF,
    campo_conta,
    com_unidade,
    num,
    resposta,
    valor_campo,
)
from app.schemas import Processo


def descrever_strings(processo: Processo) -> list[str]:
    kit = processo.kit
    assert kit is not None
    if not kit.strings:
        return [f"{A_INFORMAR}: configuração de strings não definida."]
    linhas = []
    for s in sorted(kit.strings, key=lambda s: s.mppt):
        tensao = s.modulos_em_serie * kit.modulo.voc_v
        texto = (
            f"MPPT {s.mppt}: {s.modulos_em_serie} módulos em série "
            f"(Voc da string a 25 °C: {num(tensao, 1)} V)"
        )
        if s.sugerida:
            texto += " - sugerida pelo agente, a confirmar pelo engenheiro"
        linhas.append(texto)
    return linhas


def gerar_memorial(processo: Processo, pasta: Path) -> Path:
    if processo.kit is None:
        raise ValueError("Kit ausente: não dá para gerar o memorial descritivo.")
    kit = processo.kit
    inv = kit.inversor
    mod = kit.modulo
    visita = processo.visita

    pdf = DocPDF("Memorial Descritivo - Microgeração Fotovoltaica", processo)
    pdf.alias_nb_pages()

    pdf.secao("1. Objetivo")
    pdf.paragrafo(
        "Descrever a central de microgeração fotovoltaica conectada à rede de baixa tensão da "
        "Enel por meio de inversor, conforme a norma CNC-NDBR-DBR-18-0122-EDBR "
        "v05 (Anexo B, forma de conexão 1), a Lei 14.300/2022 e a REN ANEEL 1.000/2021."
    )

    pdf.secao("2. Identificação")
    pdf.campo("Titular", campo_conta(processo, "titular"))
    pdf.campo("Código da UC", campo_conta(processo, "uc"))
    pdf.campo(
        "Endereço",
        f"{campo_conta(processo, 'endereco')} - {campo_conta(processo, 'cidade')}",
    )
    pdf.campo(
        "Classe / subgrupo",
        f"{campo_conta(processo, 'classe')} / {campo_conta(processo, 'subgrupo')}",
    )
    pdf.campo(
        "Ligação / tensão",
        f"{campo_conta(processo, 'tipo_ligacao')}, {campo_conta(processo, 'tensao_atendimento_v')} V",
    )

    pdf.secao("3. Gerador fotovoltaico")
    pdf.campo("Módulos", f"{kit.qtd_modulos} x {mod.fabricante} {mod.modelo}")
    pdf.campo("Potência unitária", com_unidade(mod.potencia_wp, "Wp"))
    pdf.campo(
        "Potência total dos módulos", f"{num(kit.potencia_total_wp / 1000, 2)} kWp"
    )
    pdf.campo("Voc / Isc do módulo", f"{num(mod.voc_v, 2)} V / {num(mod.isc_a, 2)} A")
    pdf.campo(
        "Coef. de temperatura de Voc",
        A_INFORMAR
        if mod.coef_temp_voc_pct_c is None
        else f"{num(mod.coef_temp_voc_pct_c, 3)} %/°C",
    )
    for i, linha in enumerate(descrever_strings(processo)):
        pdf.campo("Arranjo" if i == 0 else "", linha)

    pdf.secao("4. Inversor")
    pdf.campo("Fabricante / modelo", f"{inv.fabricante} {inv.modelo}")
    pdf.campo("Potência nominal CA", com_unidade(inv.potencia_nominal_w, "W"))
    pdf.campo("Potência máxima CC", com_unidade(inv.potencia_max_cc_w, "W"))
    pdf.campo("Tensão máxima CC", com_unidade(inv.tensao_max_cc_v, "V"))
    faixa = (
        f"{num(inv.mppt_min_v)} a {num(inv.mppt_max_v)} V"
        if inv.mppt_min_v is not None and inv.mppt_max_v is not None
        else A_INFORMAR
    )
    pdf.campo("Faixa de MPPT / nº de MPPTs", f"{faixa} / {inv.num_mppt}")
    pdf.campo("Corrente máxima de saída", com_unidade(inv.corrente_max_saida_a, "A"))
    pdf.campo("Tensão de saída", com_unidade(inv.tensao_saida_v, "V"))
    pdf.campo("Certificado INMETRO", inv.certificado_inmetro or A_INFORMAR)
    pdf.campo(
        "Potência instalada de geração", f"{num(potencia_instalada_kw(kit), 2)} kW"
    )

    pdf.secao("5. Proteções")
    pdf.campo("Disjuntor geral (padrão)", f"{valor_campo(visita.disjuntor_padrao_a)} A")
    pdf.campo("Disjuntor CA do inversor", com_unidade(visita.disjuntor_ca_a, "A"))
    pdf.campo(
        "DPS (instalação interna)",
        "Obrigatório (NBR 5410/5419; norma Enel 7.6.1.6) - especificação "
        + resposta(processo, "dps_especificacao", A_INFORMAR),
    )
    pdf.paragrafo(
        "As proteções de sub e sobretensão, sub e sobrefrequência e anti-ilhamento são "
        "incorporadas ao inversor; para microgeração não se exige redundância (norma Enel "
        "7.6.1.5). Recomenda-se proteção contra arco elétrico (AFCI) conforme NBR 16690."
    )

    pdf.secao("6. Condutores")
    pdf.campo("Cabo CA inversor-quadro", com_unidade(visita.bitola_ca_mm2, "mm²"))
    pdf.campo(
        "Distância inversor-quadro",
        com_unidade(visita.distancia_inversor_quadro_m, "m"),
    )

    pdf.secao("7. Medição")
    pdf.paragrafo(
        "Medição bidirecional de energia, a ser instalada pela distribuidora no padrão de "
        "entrada existente, conforme diagrama unifilar anexo."
    )

    pdf.secao("8. Normas de referência")
    pdf.paragrafo(
        "Lei 14.300/2022; REN ANEEL 1.000/2021; Enel CNC-NDBR-DBR-18-0122-EDBR v05; "
        "ABNT NBR 5410, NBR 5419, NBR 16149, NBR 16690; Portaria INMETRO 140/2022."
    )

    pdf.secao("9. Responsabilidade técnica")
    revisor = processo.revisado_por or "______________________"
    pdf.paragrafo(
        f"Responsável técnico: {revisor}   CREA: __________   ART nº: __________"
    )
    pdf.assinaturas(["Responsável técnico"])

    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"memorial_{processo.id}.pdf"
    pdf.output(str(caminho))
    return caminho
