"""R00: potência nominal do inversor x potência disponibilizada pelo padrão de entrada.

Parecer do engenheiro: é a regra que mais reprova no Ceará. A norma de
microgeração (CNC-NDBR-DBR-18-0122, item 7.2.4, nota 2) limita a potência
instalada à potência disponibilizada à UC, que para ligação monofásica é dada
pelo disjuntor de entrada (tabela CNC-OMBR-MAT-18-0124, 220 V x In).

Regra: P_nominal do inversor <= potência disponibilizada (reprova).
Sem disjuntor de entrada: incerta (não verificável). Roda antes de R02 e R03.
Premissa declarada: a vigência da tabela precisa ser confirmada (a Enel está
renomeando as normas para GRI-EDBR-CNC-GRI-00xx).
"""

from __future__ import annotations

from app.core.parecer.comum import Parecer, br, numero_do_campo, texto_do_campo
from app.schemas import Camada, Processo, ResultadoRegra

TENSAO_MONOFASICA_V = 220.0

# Disjuntor de entrada (A) -> potência disponibilizada (kW), ligação monofásica.
# Quatro primeiras linhas do corpo da norma; 50 A e 63 A do anexo.
POTENCIA_DISPONIBILIZADA_KW: dict[float, float] = {
    20: 4.40,
    25: 5.50,
    32: 7.04,
    40: 8.80,
    50: 11.00,
    63: 13.86,
}

FONTE = (
    "Norma Enel CNC-NDBR-DBR-18-0122 v05, item 7.2.4, nota 2; "
    "tabela CNC-OMBR-MAT-18-0124 (ligação monofásica)"
)
PREMISSA_VIGENCIA = (
    "tabela de potência disponibilizada da CNC-OMBR-MAT-18-0124 considerada vigente "
    "(confirmar: a Enel está renomeando as normas)"
)


def _monofasico(processo: Processo) -> bool | None:
    tipo = texto_do_campo(processo, "tipo_ligacao")
    if tipo is None:
        return None
    return tipo.strip().lower().startswith("mono")


def avaliar(processo: Processo) -> ResultadoRegra:
    p = Parecer(
        "R00",
        "Potência do inversor dentro da potência disponibilizada pelo padrão de entrada",
        Camada.DISTRIBUIDORA,
        FONTE,
    )
    if processo.kit is None:
        return p.incerta("Kit ausente: não há potência de inversor para comparar.")
    potencia_kw = processo.kit.inversor.potencia_nominal_w / 1000
    p.valores["potencia_inversor_kw"] = potencia_kw

    monofasico = _monofasico(processo)
    if monofasico is False:
        return p.nao_verificada(
            "A tabela de potência disponibilizada usada cobre só ligação monofásica."
        )
    if monofasico is None:
        p.premissas.append("ligação monofásica (tipo de ligação não lido na conta)")

    disjuntor, confiavel = numero_do_campo(processo.visita.disjuntor_padrao_a)
    if disjuntor is None:
        return p.incerta(
            "Não verificável: falta a corrente do disjuntor do padrão de entrada."
        )
    p.valores["disjuntor_entrada_a"] = disjuntor
    if not confiavel:
        return p.incerta(
            f"Disjuntor do padrão lido como {br(disjuntor, 0)} A com baixa confiança; "
            "confirme a corrente antes de conferir a potência."
        )

    if disjuntor in POTENCIA_DISPONIBILIZADA_KW:
        disponivel = POTENCIA_DISPONIBILIZADA_KW[disjuntor]
        p.premissas.append(PREMISSA_VIGENCIA)
    else:
        disponivel = round(TENSAO_MONOFASICA_V * disjuntor / 1000, 2)
        p.alertas.append(
            f"Disjuntor de {br(disjuntor, 0)} A fora da tabela da norma; potência "
            "disponibilizada calculada por 220 V x In."
        )
    p.valores["potencia_disponibilizada_kw"] = disponivel

    if potencia_kw > disponivel:
        return p.reprovada(
            f"Inversor de {br(potencia_kw, 2)} kW acima da potência disponibilizada pelo "
            f"padrão de {br(disjuntor, 0)} A ({br(disponivel, 2)} kW). A Enel reprova: "
            "aumente o padrão de entrada ou reduza o inversor."
        )
    return p.aprovada(
        f"Inversor de {br(potencia_kw, 2)} kW dentro da potência disponibilizada pelo "
        f"padrão de {br(disjuntor, 0)} A ({br(disponivel, 2)} kW)."
    )
