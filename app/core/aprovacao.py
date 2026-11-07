"""Condições mínimas das regras para aprovar e protocolar.

Passar aqui não comprova conformidade integral: o checklist documental e as
fontes de cada especificação também precisam ser fechados (docs/status-dev-a.md).

Premissas e alertas não bloqueiam: aparecem na revisão para o engenheiro.
A R05 incerta que o engenheiro confirmou (R05 em cascata, passo 3) não bloqueia.
"""

from collections import Counter

from app.schemas import Processo, ResultadoRegra, StatusRegra

REGRAS_OBRIGATORIAS = frozenset({"R00", "R01", "R02", "R03", "R04", "R05"})


def _pendente(regra: ResultadoRegra) -> bool:
    if regra.regra_id == "R05":
        from app.core.parecer.r05_inmetro import bloqueia

        return bloqueia(regra) or regra.a_validar
    return regra.status != StatusRegra.APROVADA or regra.a_validar


def bloqueios_regras(processo: Processo) -> list[str]:
    contagem = Counter(r.regra_id for r in processo.regras)
    bloqueios = [
        f"{id_}: conferência ausente"
        for id_ in sorted(REGRAS_OBRIGATORIAS - contagem.keys())
    ]
    for regra in processo.regras:
        if contagem[regra.regra_id] > 1:
            bloqueios.append(f"{regra.regra_id}: resultado duplicado")
        if regra.status == StatusRegra.REPROVADA:
            bloqueios.append(f"{regra.regra_id}: reprovada — {regra.mensagem}")
        elif regra.regra_id in REGRAS_OBRIGATORIAS and _pendente(regra):
            bloqueios.append(
                f"{regra.regra_id}: verificação pendente — {regra.mensagem}"
            )
    return list(dict.fromkeys(bloqueios))
