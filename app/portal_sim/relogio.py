"""Relógio simulado. Toda data do sistema sai de hoje(), nunca de date.today().

A data fica no SQLite (tabela relogio). Na primeira leitura ela começa em
RELOGIO_INICIO (AAAA-MM-DD, no .env); sem essa variável, começa na data real
do servidor. Este é o único ponto do sistema que lê a data real.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

from app.tracing.db import conectar


def _data_inicial() -> date:
    inicio = os.environ.get("RELOGIO_INICIO")
    if inicio:
        return date.fromisoformat(inicio)
    return date.today()  # único uso permitido: semente do relógio simulado


def hoje() -> date:
    """Data atual no relógio simulado."""
    with conectar() as con:
        linha = con.execute("SELECT data FROM relogio WHERE id = 1").fetchone()
        if linha:
            return date.fromisoformat(linha[0])
        inicial = _data_inicial()
        con.execute(
            "INSERT INTO relogio (id, data) VALUES (1, ?)", (inicial.isoformat(),)
        )
        return inicial


def definir_data(nova: date) -> date:
    """Coloca o relógio numa data exata (reset da demo e testes)."""
    with conectar() as con:
        con.execute(
            "INSERT INTO relogio (id, data) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET data = excluded.data",
            (nova.isoformat(),),
        )
    return nova


def avancar_tempo(dias: int) -> date:
    """Avança o relógio simulado em `dias` corridos e devolve a nova data."""
    if dias < 0:
        raise ValueError("o relógio simulado só anda para frente")
    return definir_data(hoje() + timedelta(days=dias))
