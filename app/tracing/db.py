"""Conexão SQLite usada pelo tracing e pelo relógio simulado.

O caminho vem de DB_PATH no .env (padrão: data/app.db). Testes apontam
DB_PATH para um arquivo temporário.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS passos_trace (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    processo_id TEXT NOT NULL,
    json TEXT NOT NULL,
    prompts TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS ix_passos_trace_processo ON passos_trace(processo_id);
CREATE TABLE IF NOT EXISTS relogio (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL
);
"""


def caminho_db() -> Path:
    return Path(os.environ.get("DB_PATH", "data/app.db"))


def conectar() -> sqlite3.Connection:
    caminho = caminho_db()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(caminho)
    con.executescript(_ESQUEMA)
    colunas = {linha[1] for linha in con.execute("PRAGMA table_info(passos_trace)")}
    if "prompts" not in colunas:  # banco local criado antes dos prompts versionados
        con.execute(
            "ALTER TABLE passos_trace ADD COLUMN prompts TEXT NOT NULL DEFAULT '[]'"
        )
        con.commit()
    return con
