"""R03: tensão das strings no frio, corrente por MPPT e janela do MPPT.

Parecer do engenheiro (posição consolidada):
- Voc_frio = Voc_STC x [1 + (β/100) x (Tmin - 25)], β do datasheet (%/°C).
  Tensão da string = N x Voc_frio. Acima de 100% da tensão máxima CC do inversor
  reprova; acima de 95% alerta.
- Tabela de correção em paralelo, só como verificação: se só ela passar de 100%,
  alerta. Sem β no datasheet, a tabela vira o método e a regra sai "aprovada com
  premissa assumida" (ou reprovada pela tabela).
- Tmin por área de concessão (o integrador escolhe a área; mapeamento por
  município fica para depois do hackathon).
- Corrente: Isc das strings em paralelo acima do limite do MPPT reprova;
  1,25 x Isc acima do limite alerta. Fora da janela do MPPT: alerta.
"""

from __future__ import annotations

from collections import Counter

from app.core.parecer.comum import Parecer, br
from app.schemas import Camada, Processo, ResultadoRegra

# Temperatura mínima adotada por área (°C) e observação do parecer
TMIN_POR_AREA: dict[str, tuple[float, str | None]] = {
    "ceara": (10, None),
    "sao_paulo": (-3, None),
    "rj_serra": (0, None),
    "rj_sul_fluminense": (-5, "Tmin do Sul Fluminense provisória, a confirmar"),
    "rj_demais": (0, None),
}

# NEC 690.7(A): fator de correção do Voc pela temperatura mínima (fonte secundária)
_TABELA_NEC = (
    (20, 1.02),
    (15, 1.04),
    (10, 1.06),
    (5, 1.08),
    (0, 1.10),
    (-5, 1.12),
    (-10, 1.14),
    (-15, 1.16),
    (-20, 1.18),
)

LIMIAR_REPROVA = 1.00
LIMIAR_ALERTA = 0.95
FATOR_CORRENTE = 1.25

FONTE = (
    "Datasheets do módulo e do inversor; correção de Voc pelo coeficiente β "
    "(tabela NEC 690.7(A) como verificação); parecer do engenheiro"
)


def fator_beta(beta_pct_c: float, tmin_c: float) -> float:
    return 1 + (beta_pct_c / 100) * (tmin_c - 25)


def fator_tabela(tmin_c: float) -> float | None:
    """Fator da tabela para a faixa que contém Tmin; None abaixo de -20 °C."""
    if tmin_c > 24:
        return 1.0
    for limite_inferior, fator in _TABELA_NEC:
        if tmin_c >= limite_inferior:
            return fator
    return None


def avaliar(processo: Processo) -> ResultadoRegra:
    p = Parecer(
        "R03",
        "Tensão das strings no frio, corrente e janela do MPPT dentro dos limites do inversor",
        Camada.TECNICA,
        FONTE,
    )
    kit = processo.kit
    if kit is None:
        return p.incerta("Kit ausente.")
    if not kit.strings:
        return p.incerta("Configuração de strings não definida.")
    mod, inv = kit.modulo, kit.inversor
    if any(s.sugerida for s in kit.strings):
        p.premissas.append("configuração de strings sugerida pelo agente, a confirmar")

    area = processo.visita.area_concessao
    if area is None:
        return p.incerta(
            "Não verificável: informe a área de concessão para definir a temperatura mínima."
        )
    if area not in TMIN_POR_AREA:
        return p.incerta(
            f"Área de concessão '{area}' sem temperatura mínima cadastrada."
        )
    tmin, obs = TMIN_POR_AREA[area]
    if obs:
        p.premissas.append(obs)
    p.valores.update({"tmin_c": tmin, "tensao_max_cc_v": inv.tensao_max_cc_v})

    f_tab = fator_tabela(tmin)
    beta = mod.coef_temp_voc_pct_c
    if beta is not None:
        fator = fator_beta(beta, tmin)
        metodo = f"β {br(beta, 3)} %/°C"
    elif f_tab is not None:
        fator = f_tab
        metodo = "tabela NEC 690.7(A)"
        p.premissas.append(
            "coeficiente β ausente no datasheet; Voc corrigido pela tabela"
        )
    else:
        return p.incerta("Sem β e Tmin abaixo da tabela de correção.")
    voc_frio = mod.voc_v * fator
    p.valores.update(
        {"fator_correcao": round(fator, 5), "voc_frio_v": round(voc_frio, 2)}
    )

    reprovas: list[str] = []
    pior = max(kit.strings, key=lambda s: s.modulos_em_serie)
    maior_n = pior.modulos_em_serie
    tensao = maior_n * voc_frio
    uso = tensao / inv.tensao_max_cc_v
    p.valores.update(
        {
            "modulos_em_serie_max": maior_n,
            "tensao_string_v": round(tensao, 1),
            "uso_tensao_max_pct": round(uso * 100, 1),
        }
    )
    if uso > LIMIAR_REPROVA:
        reprovas.append(
            f"MPPT {pior.mppt}: string de {maior_n} módulos chega a {br(tensao)} V no frio "
            f"({br(uso * 100)}% de {br(inv.tensao_max_cc_v, 0)} V)"
        )
    elif uso > LIMIAR_ALERTA:
        p.alertas.append(
            f"MPPT {pior.mppt}: string de {maior_n} módulos a {br(uso * 100)}% da tensão "
            "máxima CC no frio."
        )
    if beta is not None and f_tab is not None:
        uso_tab = maior_n * mod.voc_v * f_tab / inv.tensao_max_cc_v
        if uso_tab > LIMIAR_REPROVA >= uso:
            p.alertas.append(
                f"Pela tabela de correção a string chegaria a {br(uso_tab * 100)}% da tensão "
                "máxima; o datasheet (mais específico) aprova."
            )

    # Corrente por MPPT: strings em paralelo no mesmo MPPT somam Isc
    if inv.corrente_max_entrada_a is None:
        p.alertas.append(
            "Corrente máxima por MPPT não informada: corrente não verificada."
        )
    else:
        for mppt, n_paralelo in sorted(Counter(s.mppt for s in kit.strings).items()):
            isc = n_paralelo * mod.isc_a
            if isc > inv.corrente_max_entrada_a:
                reprovas.append(
                    f"MPPT {mppt}: Isc de {br(isc)} A acima do limite de "
                    f"{br(inv.corrente_max_entrada_a)} A"
                )
            elif FATOR_CORRENTE * isc > inv.corrente_max_entrada_a:
                p.alertas.append(
                    f"MPPT {mppt}: 1,25 x Isc = {br(FATOR_CORRENTE * isc)} A acima do limite "
                    f"de {br(inv.corrente_max_entrada_a)} A (margem não exigida pelo fabricante)."
                )

    # Janela do MPPT: alerta, a string ainda opera parcialmente
    if (
        mod.vmp_v is not None
        and inv.mppt_min_v is not None
        and inv.mppt_max_v is not None
    ):
        for s in kit.strings:
            vmp = s.modulos_em_serie * mod.vmp_v
            if not inv.mppt_min_v <= vmp <= inv.mppt_max_v:
                p.alertas.append(
                    f"MPPT {s.mppt}: Vmp da string ({br(vmp)} V) fora da janela "
                    f"{br(inv.mppt_min_v, 0)}-{br(inv.mppt_max_v, 0)} V."
                )

    if reprovas:
        return p.reprovada("Reprovado: " + "; ".join(reprovas) + ".")
    return p.aprovada(
        f"String de {maior_n} módulos: {br(tensao)} V no frio ({br(tmin, 0)} °C, {metodo}), "
        f"{br(uso * 100)}% de {br(inv.tensao_max_cc_v, 0)} V."
    )
