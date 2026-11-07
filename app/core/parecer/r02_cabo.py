"""R02: disjuntor CA x cabo CA no trecho inversor-quadro.

Parecer do engenheiro (posição consolidada):
- Critério: Ib <= In <= Iz corrigido (reprova). Ib = corrente máxima de saída CA do
  datasheet. Iz da NBR 5410 Tabela 36 (cobre, PVC 70 °C, 2 condutores carregados)
  vezes os fatores de temperatura e de agrupamento.
- O manual do inversor é restrição adicional (disjuntor máximo, fator mínimo,
  cabo mínimo, faixa dos bornes). O fator 1,25 só entra se o cadastro indicar.
- Dado ausente vira premissa declarada: método B2, PVC, ambiente interno (35 °C),
  2 circuitos agrupados (0,80). Cabo exposto ao sol ou em forro: 50 °C (0,71).
- Queda de tensão no trecho CA: acima de 4% reprova (NBR 5410 6.2.7.2), acima de
  2% alerta. O comprimento é dado obrigatório: sem ele, a regra fica incerta.
- 2,5 mm² é piso, mas o Iz domina. Icc, polos e DR são dados pedidos, não motivo
  de reprovação.
- XLPE (Tabela 37) ainda não validada pelo engenheiro: cabo XLPE fica incerto.
"""

from __future__ import annotations

from app.core.parecer.comum import Parecer, br
from app.schemas import Camada, Processo, ResultadoRegra

# NBR 5410 Tabela 36: capacidade de condução (A), cobre, PVC 70 °C,
# 2 condutores carregados, temperatura ambiente 30 °C.
SECOES_MM2 = (1.5, 2.5, 4, 6, 10, 16, 25, 35)
IZ_PVC_TABELA_36: dict[str, tuple[float, ...]] = {
    "A1": (14.5, 19.5, 26, 34, 46, 61, 80, 99),
    "A2": (14, 18.5, 25, 32, 43, 57, 75, 92),
    "B1": (17.5, 24, 32, 41, 57, 76, 101, 125),
    "B2": (16.5, 23, 30, 38, 52, 69, 90, 111),
    "C": (19.5, 27, 36, 46, 63, 85, 112, 138),
}

# NBR 5410 Tabela 40 (PVC): fator de correção de temperatura ambiente
FATOR_TEMPERATURA_PVC = {"interno": (35, 0.94), "exposto": (50, 0.71)}
# NBR 5410 Tabela 42 (feixe): fator de agrupamento por número de circuitos
FATOR_AGRUPAMENTO = {1: 1.00, 2: 0.80, 3: 0.70, 4: 0.65, 5: 0.60}

RESISTIVIDADE_COBRE_70C = 0.0214  # ohm.mm²/m
QUEDA_MAX_PCT = 4.0  # NBR 5410 6.2.7.2
QUEDA_ALERTA_PCT = 2.0  # prática, não norma
SECAO_MINIMA_MM2 = 2.5

FONTE = "NBR 5410 (Tabelas 36, 40 e 42; 6.2.7.2); manual do inversor como restrição adicional"


def queda_tensao_pct(
    corrente_a: float, comprimento_m: float, secao_mm2: float, tensao_v: float
) -> float:
    """Queda monofásica (ida e volta): 2·ρ·L·I / (S·V), em %."""
    return (
        2
        * RESISTIVIDADE_COBRE_70C
        * comprimento_m
        * corrente_a
        / (secao_mm2 * tensao_v)
        * 100
    )


def iz_corrigido(
    secao_mm2: float, metodo: str, ambiente: str, circuitos: int
) -> tuple[float, float, float, float]:
    """(Iz tabela, fator temperatura, fator agrupamento, Iz corrigido)."""
    iz = IZ_PVC_TABELA_36[metodo][SECOES_MM2.index(secao_mm2)]
    kt = FATOR_TEMPERATURA_PVC[ambiente][1]
    kg = FATOR_AGRUPAMENTO[circuitos]
    return iz, kt, kg, round(iz * kt * kg, 1)


def avaliar(processo: Processo) -> ResultadoRegra:
    p = Parecer(
        "R02",
        "Disjuntor CA entre a corrente de saída do inversor e a capacidade do cabo",
        Camada.TECNICA,
        FONTE,
    )
    if processo.kit is None:
        return p.incerta("Kit ausente: não há corrente de saída para conferir.")
    inv = processo.kit.inversor
    v = processo.visita
    ib = inv.corrente_max_saida_a
    tensao = inv.tensao_saida_v
    p.valores.update({"ib_a": ib, "tensao_v": tensao})

    faltando: list[str] = []
    if v.disjuntor_ca_a is None:
        faltando.append("disjuntor CA")
    if v.bitola_ca_mm2 is None:
        faltando.append("seção do cabo CA")
    if v.distancia_inversor_quadro_m is None:
        faltando.append("comprimento do cabo CA (inversor-quadro)")

    # Premissas para o que não foi informado
    metodo = v.metodo_instalacao or "B2"
    if v.metodo_instalacao is None:
        p.premissas.append("método de instalação B2 (não informado)")
    if v.isolacao is None:
        p.premissas.append("isolação PVC 70 °C (não informada)")
    elif v.isolacao == "XLPE":
        return p.incerta(
            "Cabo XLPE/HEPR usa a Tabela 37 da NBR 5410, ainda não validada pelo "
            "engenheiro neste sistema; confira a capacidade do cabo manualmente."
        )
    ambiente = v.ambiente_cabo or "interno"
    if v.ambiente_cabo is None:
        p.premissas.append("cabo em ambiente interno, 35 °C (não informado)")
    circuitos = v.circuitos_agrupados or 2
    if v.circuitos_agrupados is None:
        p.premissas.append("2 circuitos agrupados, fator 0,80 (não informado)")
    elif circuitos not in FATOR_AGRUPAMENTO:
        return p.incerta(
            f"{circuitos} circuitos agrupados: fator de agrupamento fora da faixa "
            "implementada (1 a 5); confira manualmente."
        )
    if v.icc_ka is not None:
        p.alertas.append(
            f"Icc informado ({br(v.icc_ka, 1)} kA): a capacidade de interrupção do "
            "disjuntor não é verificada neste sistema."
        )

    reprovas: list[str] = []
    in_ = v.disjuntor_ca_a
    secao = v.bitola_ca_mm2
    if in_ is not None:
        p.valores["in_a"] = in_
        if ib > in_:
            reprovas.append(
                f"corrente de saída ({br(ib)} A) acima do disjuntor de {br(in_, 0)} A"
            )
        if inv.disjuntor_max_a is not None and in_ > inv.disjuntor_max_a:
            reprovas.append(
                f"disjuntor de {br(in_, 0)} A acima do máximo do manual "
                f"({br(inv.disjuntor_max_a, 0)} A)"
            )
        if inv.fator_min_disjuntor is not None and in_ < inv.fator_min_disjuntor * ib:
            reprovas.append(
                f"manual exige disjuntor de pelo menos {br(inv.fator_min_disjuntor, 2)} x Ib "
                f"= {br(inv.fator_min_disjuntor * ib)} A"
            )

    if secao is not None:
        p.valores["secao_mm2"] = secao
        if secao < SECAO_MINIMA_MM2:
            reprovas.append(f"seção de {br(secao)} mm² abaixo do piso de 2,5 mm²")
        if inv.cabo_min_mm2 is not None and secao < inv.cabo_min_mm2:
            reprovas.append(
                f"seção abaixo do mínimo do manual ({br(inv.cabo_min_mm2)} mm²)"
            )
        if (
            inv.terminal_ca_min_mm2 is not None and secao < inv.terminal_ca_min_mm2
        ) or (inv.terminal_ca_max_mm2 is not None and secao > inv.terminal_ca_max_mm2):
            reprovas.append("seção fora da faixa aceita pelos bornes CA do inversor")
        if secao not in SECOES_MM2:
            return p.incerta(
                f"Seção de {br(secao)} mm² fora da tabela implementada; confira manualmente."
            )
        iz, kt, kg, izc = iz_corrigido(secao, metodo, ambiente, circuitos)
        p.valores.update(
            {
                "iz_tabela_a": iz,
                "fator_temperatura": kt,
                "fator_agrupamento": kg,
                "iz_corrigido_a": izc,
                "metodo": metodo,
            }
        )
        if in_ is not None and in_ > izc:
            reprovas.append(
                f"disjuntor de {br(in_, 0)} A acima da capacidade corrigida do cabo "
                f"({br(izc)} A em {br(secao)} mm², método {metodo})"
            )
        if v.distancia_inversor_quadro_m is not None:
            queda = round(
                queda_tensao_pct(ib, v.distancia_inversor_quadro_m, secao, tensao), 2
            )
            p.valores.update(
                {
                    "comprimento_m": v.distancia_inversor_quadro_m,
                    "queda_tensao_pct": queda,
                }
            )
            if queda > QUEDA_MAX_PCT:
                reprovas.append(
                    f"queda de tensão de {br(queda, 2)}% acima de 4% (NBR 5410 6.2.7.2)"
                )
            elif queda > QUEDA_ALERTA_PCT:
                p.alertas.append(
                    f"Queda de tensão de {br(queda, 2)}% acima de 2%: consome a folga "
                    "até o desarme por sobretensão do inversor."
                )

    if reprovas:
        return p.reprovada("Reprovado: " + "; ".join(reprovas) + ".")
    if faltando:
        return p.incerta("Não verificável sem: " + ", ".join(faltando) + ".")
    return p.aprovada(
        f"Ib {br(ib)} A <= In {br(in_, 0)} A <= Iz corrigido {br(p.valores['iz_corrigido_a'])} A "
        f"({br(secao)} mm², método {metodo}); queda de tensão de "
        f"{br(p.valores['queda_tensao_pct'], 2)}%."
    )
