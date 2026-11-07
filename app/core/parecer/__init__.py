"""Regras revisadas a partir do parecer do engenheiro (07/11/2026).

Cada módulo expõe uma função `avaliar(processo) -> ResultadoRegra` completa,
com alertas, premissas e evidências (campos novos do contrato):

    R00  potência do inversor x disjuntor do padrão de entrada   (r00_potencia)
    R02  disjuntor CA x cabo CA: Ib <= In <= Iz corrigido, queda (r02_cabo)
    R03  tensão das strings no frio, corrente e janela do MPPT    (r03_strings)
    R05  INMETRO em cascata: consulta, catálogo, datasheet         (r05_inmetro)

Integração (Dev A): em app/core/regras.py, `conferir` passa a chamar estas
funções para R00, R02, R03 e R05. Ver docs/parecer-regras.md.
"""

from app.core.parecer.r00_potencia import avaliar as avaliar_r00
from app.core.parecer.r02_cabo import avaliar as avaliar_r02
from app.core.parecer.r03_strings import avaliar as avaliar_r03
from app.core.parecer.r05_inmetro import avaliar as avaliar_r05

REGRAS_PARECER = {
    "R00": avaliar_r00,
    "R02": avaliar_r02,
    "R03": avaliar_r03,
    "R05": avaliar_r05,
}

__all__ = ["REGRAS_PARECER", "avaliar_r00", "avaliar_r02", "avaliar_r03", "avaliar_r05"]
