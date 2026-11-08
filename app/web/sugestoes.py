"""Respostas de exemplo que já vêm preenchidas nas perguntas abertas.

Quem testa a demonstração não sabe o telefone do titular nem a especificação do
DPS: cada pergunta chega com um valor plausível, no formato que a API aceita, e
um clique em "Responder" manda tudo. O integrador de verdade troca o que não
servir antes de enviar.
"""

from __future__ import annotations

from app.core.arranjo import bitola_por_tabela
from app.schemas import Pergunta, Processo

_FIXAS = {
    "telefone": "(85) 99999-0000",
    "qtd_ucs_credito": "1",
    "modalidade_compensacao": "Autoconsumo local",
    "dps_especificacao": "Classe II, 275 V, 20 kA",
    "relacao_cargas": "Geladeira 150 W x1\nChuveiro elétrico 5500 W x1\nTelevisor 100 W x2",
    "disjuntor_padrao_a": "50",
    "distancia_inversor_quadro_m": "8",
    "coordenadas_padrao": "-3.7368, -38.4931",
    "area_concessao": "Ceará",
    "tipo_ramal": "Aéreo",
    "email_contato": "integrador@exemplo.com",
    "coef_temp_voc_pct_c": "-0,27",
    "certificado_inmetro": "SIM-004314/2024",
}


def sugestao(p: Processo, q: Pergunta) -> str:
    if q.campo.startswith("campos."):
        lido = p.campos.get(q.campo.removeprefix("campos."))
        return "" if lido is None or lido.valor is None else str(lido.valor)
    if q.campo == "bitola_ca_mm2":
        disjuntor = p.visita.disjuntor_ca_a
        bitola = bitola_por_tabela(disjuntor) if disjuntor else None
        return f"{bitola:g}" if bitola else "6"
    if q.campo == "strings":
        sugeridas = p.kit is not None and any(s.sugerida for s in p.kit.strings)
        return "sim" if sugeridas else ""
    return _FIXAS.get(q.campo, "")


def sugestoes(p: Processo) -> dict[str, str]:
    return {q.id: sugestao(p, q) for q in p.perguntas if not q.resposta}
