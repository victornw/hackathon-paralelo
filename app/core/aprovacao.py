"""Condições mínimas das regras para aprovar e protocolar.

Passar aqui não comprova conformidade integral: o checklist documental e as
fontes de cada especificação também precisam ser fechados (docs/status-dev-a.md).
"""

from collections import Counter

from app.schemas import Processo, StatusRegra

REGRAS_OBRIGATORIAS = frozenset({"R01", "R02", "R03", "R04", "R05"})


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
        elif regra.regra_id in REGRAS_OBRIGATORIAS and (
            regra.status != StatusRegra.APROVADA or regra.a_validar
        ):
            bloqueios.append(
                f"{regra.regra_id}: verificação pendente — {regra.mensagem}"
            )
    return list(dict.fromkeys(bloqueios))
