"""Solicitação de orçamento de conexão (Anexo A da norma Enel CNC-NDBR-DBR-18-0122).

Preenche a partir da conta de luz (Processo.campos), do kit e da visita.
Dado ausente aparece como "A INFORMAR"; nada é presumido.
"""

from __future__ import annotations

from pathlib import Path

from app.docs.pdf_base import (
    A_INFORMAR,
    DocPDF,
    campo_conta,
    com_unidade,
    num,
    resposta,
    valor_campo,
)
from app.schemas import Kit, Processo


def potencia_instalada_kw(kit: Kit) -> float:
    """Menor valor entre a soma dos módulos e a potência nominal do inversor
    (critério da REN 1.000 para centrais fotovoltaicas; validar com engenheiro)."""
    return min(kit.potencia_total_wp, kit.inversor.potencia_nominal_w) / 1000


def carga_instalada_kw(processo: Processo) -> float | None:
    cargas = processo.visita.relacao_cargas
    if not cargas:
        return None
    return sum(c.potencia_w * c.quantidade for c in cargas) / 1000


def gerar_anexo_a(processo: Processo, pasta: Path) -> Path:
    if processo.kit is None:
        raise ValueError(
            "Kit ausente: não dá para preencher a solicitação de orçamento."
        )
    kit = processo.kit
    inv = kit.inversor
    visita = processo.visita

    pdf = DocPDF(
        "Solicitação de Orçamento de Conexão - Microgeração (Anexo A)", processo
    )
    pdf.alias_nb_pages()

    pdf.secao("1. Identificação da unidade consumidora")
    pdf.campo("Código da UC", campo_conta(processo, "uc"))
    pdf.campo("Titular", campo_conta(processo, "titular"))
    pdf.campo("CPF/CNPJ", campo_conta(processo, "cpf_cnpj"))
    pdf.campo("Endereço", campo_conta(processo, "endereco"))
    pdf.campo("Município", campo_conta(processo, "cidade"))
    pdf.campo(
        "Classe / subgrupo",
        f"{campo_conta(processo, 'classe')} / {campo_conta(processo, 'subgrupo')}",
    )
    pdf.campo("Tipo de ligação", campo_conta(processo, "tipo_ligacao"))
    pdf.campo(
        "Tensão de atendimento", f"{campo_conta(processo, 'tensao_atendimento_v')} V"
    )
    pdf.campo(
        "Disjuntor do padrão de entrada", f"{valor_campo(visita.disjuntor_padrao_a)} A"
    )
    pdf.campo("Tipo de ramal", visita.tipo_ramal or A_INFORMAR)
    coords = (
        f"{num(visita.latitude, 5)}, {num(visita.longitude, 5)}"
        if visita.latitude is not None and visita.longitude is not None
        else A_INFORMAR
    )
    pdf.campo("Coordenadas do padrão (lat, long)", coords)
    pdf.campo("E-mail de contato", processo.email_contato or A_INFORMAR)

    pdf.secao("2. Carga instalada")
    if visita.relacao_cargas:
        linhas = [
            [
                c.descricao,
                str(c.quantidade),
                num(c.potencia_w),
                num(c.potencia_w * c.quantidade),
            ]
            for c in visita.relacao_cargas
        ]
        pdf.tabela(
            ["Equipamento", "Qtd.", "Potência (W)", "Total (W)"],
            linhas,
            [94, 16, 32, 32],
        )
    pdf.campo(
        "Carga instalada total", com_unidade(carga_instalada_kw(processo), "kW", 2)
    )

    pdf.secao("3. Dados da geração")
    pdf.campo("Fonte", "Solar fotovoltaica")
    pdf.campo("Tipo de geração", "Empregando inversor")
    pdf.campo(
        "Potência dos módulos",
        f"{kit.qtd_modulos} x {num(kit.modulo.potencia_wp)} Wp = {num(kit.potencia_total_wp / 1000, 2)} kWp",
    )
    pdf.campo(
        "Potência instalada de geração", f"{num(potencia_instalada_kw(kit), 2)} kW"
    )
    pdf.campo(
        "Modalidade de compensação",
        resposta(processo, "modalidade_compensacao", A_INFORMAR),
    )

    pdf.secao("4. Dados do inversor")
    pdf.campo("Fabricante", inv.fabricante)
    pdf.campo("Modelo", inv.modelo)
    pdf.campo("Quantidade", "1")
    pdf.campo("Potência nominal", com_unidade(inv.potencia_nominal_w, "W"))
    pdf.campo("Tensão nominal de saída", com_unidade(inv.tensao_saida_v, "V"))
    pdf.campo("Certificado INMETRO", inv.certificado_inmetro or A_INFORMAR)

    pdf.secao("5. Dados dos módulos")
    pdf.campo("Fabricante / modelo", f"{kit.modulo.fabricante} {kit.modulo.modelo}")
    pdf.campo("Quantidade", str(kit.qtd_modulos))
    pdf.campo("Potência unitária", com_unidade(kit.modulo.potencia_wp, "Wp"))

    pdf.secao("6. Declarações")
    pdf.paragrafo(
        "Declaro que as informações acima são verdadeiras, que a instalação atende às normas "
        "técnicas da ABNT e à norma CNC-NDBR-DBR-18-0122 da Enel, e que o inversor possui "
        "certificado INMETRO (Portaria 140/2022) para a tensão nominal de conexão."
    )
    pdf.assinaturas(
        ["Titular da UC ou procurador", "Responsável técnico (ART nº ______)"]
    )

    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"solicitacao_orcamento_{processo.id}.pdf"
    pdf.output(str(caminho))
    return caminho
