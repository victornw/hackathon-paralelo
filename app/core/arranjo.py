"""Tabelas e conferências do arranjo FV: disjuntor CA, cabo CA e strings.

O agente não dimensiona o sistema: ele confere o kit vendido e escolhe
disjuntor e cabo por tabela. Tudo aqui é determinístico e as tabelas estão
marcadas como "a validar" até um engenheiro revisá-las.
"""

from __future__ import annotations

from datetime import datetime

from app.schemas import DadosVisita, Kit, Processo, ResultadoRegra, StringFV
from app.tracing import registrar_uso, trace

# Disjuntores termomagnéticos padrão (A). A validar com engenheiro.
DISJUNTORES_A: tuple[float, ...] = (10, 16, 20, 25, 32, 40, 50, 63)

# NBR 5410, Tabela 36: cobre/PVC 70 °C, método B1, 2 condutores carregados (A).
# A validar com engenheiro.
CABO_IZ_A: dict[float, float] = {
    1.5: 17.5,
    2.5: 24,
    4: 32,
    6: 41,
    10: 57,
    16: 76,
    25: 101,
}

# Temperatura mínima fixa para a tensão de circuito aberto a frio. A validar
# com engenheiro: o valor real depende do local da instalação.
T_MIN_C = 10.0
T_REFERENCIA_C = 25.0

# Os templates de unifilar só cobrem 1 ou 2 MPPTs.
MAX_MPPTS_PROPOSTOS = 2


def voc_corrigido_v(voc_v: float, coef_temp_pct_c: float) -> float:
    """Voc do módulo na temperatura mínima, a partir do coeficiente em %/°C."""
    return voc_v * (1 + coef_temp_pct_c / 100 * (T_MIN_C - T_REFERENCIA_C))


def disjuntor_por_tabela(corrente_a: float) -> float | None:
    """Menor disjuntor padrão com In >= Ib (parecer: Ib <= In); None se nenhum serve."""
    return next((d for d in DISJUNTORES_A if d >= corrente_a), None)


def bitola_por_tabela(disjuntor_a: float) -> float | None:
    """Menor seção cujo Iz corrigido (premissas padrão da R02: B2, PVC, 35 °C,
    2 circuitos) comporta o disjuntor. Só serve de sugestão em pergunta: nunca é
    gravada na visita. Mesma conta da R02, para o agente não sugerir cabo que a
    própria regra reprova."""
    from app.core.parecer.r02_cabo import SECOES_MM2, iz_corrigido

    return next(
        (
            s
            for s in SECOES_MM2
            if s >= 2.5 and iz_corrigido(s, "B2", "interno", 2)[3] >= disjuntor_a
        ),
        None,
    )


def _dividir(total: int, partes: int) -> list[int]:
    return [total // partes + (1 if i < total % partes else 0) for i in range(partes)]


def propor_strings(kit: Kit) -> list[StringFV]:
    """Propõe uma configuração de strings, sempre marcada como sugerida.

    Uma string no MPPT 1 se a tensão a frio cabe no inversor; senão divide por
    igual entre os MPPTs (até 2). Microinversor: cada módulo liga sozinho a uma
    entrada, então a string é de 1 módulo. Sem coeficiente de temperatura ou
    sem configuração que caiba, devolve [].
    """
    if kit.qtd_modulos <= 0:
        return []
    if kit.inversor.microinversor:
        return [StringFV(mppt=1, modulos_em_serie=1, sugerida=True)]
    coef = kit.modulo.coef_temp_voc_pct_c
    if coef is None:
        return []
    voc_frio = voc_corrigido_v(kit.modulo.voc_v, coef)
    limite = kit.inversor.tensao_max_cc_v
    for mppts in range(1, min(kit.inversor.num_mppt, MAX_MPPTS_PROPOSTOS) + 1):
        tamanhos = _dividir(kit.qtd_modulos, mppts)
        if all(n >= 1 and n * voc_frio <= limite for n in tamanhos):
            return [
                StringFV(mppt=i + 1, modulos_em_serie=n, sugerida=True)
                for i, n in enumerate(tamanhos)
            ]
    return []


@trace("verificar_arranjo")
def verificar_arranjo(
    kit: Kit, visita: DadosVisita
) -> tuple[Kit, DadosVisita, list[ResultadoRegra]]:
    """Confere o kit vendido (R03, R04), propõe strings se faltarem
    (marcadas sugerida=True) e seleciona o disjuntor CA por tabela. A bitola do
    cabo fica como o integrador informou."""
    # import tardio: regras importa as tabelas deste módulo
    from app.core.regras import avaliar_regras

    kit_novo = kit.model_copy(deep=True)
    visita_nova = visita.model_copy(deep=True)
    if not kit_novo.strings:
        kit_novo.strings = propor_strings(kit_novo)
    if visita_nova.disjuntor_ca_a is None:
        visita_nova.disjuntor_ca_a = disjuntor_por_tabela(
            kit_novo.inversor.corrente_max_saida_a
        )

    processo = Processo(
        id="verificacao_arranjo",
        criado_em=datetime.now(),
        kit=kit_novo,
        visita=visita_nova,
    )
    resultados = avaliar_regras(processo, ids=("R03", "R04"))
    registrar_uso(
        decisao=(
            f"Arranjo conferido: {len(kit_novo.strings)} string(s), "
            f"disjuntor CA {visita_nova.disjuntor_ca_a} A, "
            + ", ".join(f"{r.regra_id} {r.status.value}" for r in resultados)
            + "."
        )
    )
    return kit_novo, visita_nova, resultados
