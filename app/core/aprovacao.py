"""Condições mínimas das regras para aprovar e protocolar.

Passar aqui não comprova conformidade integral: o checklist documental e as
fontes de cada especificação também precisam ser fechados (docs/status-dev-a.md).

Premissas e alertas não bloqueiam: aparecem na revisão para o engenheiro.
A R05 incerta que o engenheiro confirmou (R05 em cascata, passo 3) não bloqueia.
"""

import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

from app.schemas import Processo, ResultadoRegra, StatusRegra

REGRAS_OBRIGATORIAS = frozenset({"R00", "R01", "R02", "R03", "R04", "R05"})


def _pendente(regra: ResultadoRegra) -> bool:
    if regra.regra_id == "R05":
        from app.core.parecer.r05_inmetro import bloqueia

        return bloqueia(regra) or regra.a_validar
    return regra.status != StatusRegra.APROVADA or regra.a_validar


# Entre aspas é a nota do unifilar que explica o marcador, não um campo vazio.
_CAMPO_VAZIO = re.compile(r'(?<!")A\s+INFORMAR(?!")')


def _campos_vazios(caminho: str) -> int:
    try:
        texto = "\n".join(pg.extract_text() or "" for pg in PdfReader(caminho).pages)
    except Exception:  # noqa: BLE001 - documento ilegível é tratado pela R01
        return 0
    return len(_CAMPO_VAZIO.findall(texto))


def bloqueios_documentos(processo: Processo) -> list[str]:
    """Pacote com campo "A INFORMAR" não vai para assinatura nem protocolo."""
    bloqueios = []
    for doc in processo.documentos:
        if doc.formato == "pdf" and Path(doc.caminho).is_file():
            n = _campos_vazios(doc.caminho)
            if n:
                bloqueios.append(
                    f"{doc.tipo}: {n} campo(s) A INFORMAR no documento gerado"
                )
    return bloqueios


def bloqueios_aprovacao(processo: Processo) -> list[str]:
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
    bloqueios.extend(bloqueios_documentos(processo))
    return list(dict.fromkeys(bloqueios))
