"""Conexão com o banco, usada por todo o app (processos, portal, relógio, trace).

Sem configuração, é um SQLite local em DB_PATH (padrão: data/app.db); testes apontam
DB_PATH para um arquivo temporário. Com TURSO_DATABASE_URL e TURSO_AUTH_TOKEN, o banco
fica no Turso (SQLite hospedado): sobrevive a deploys e reinícios do Render grátis.
Os arquivos (contas enviadas, PDFs gerados) são espelhados na tabela `arquivos` e
restaurados no disco quando o app sobe (ver espelhar_arquivo / restaurar_arquivos).
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
CREATE TABLE IF NOT EXISTS arquivos (
    caminho TEXT PRIMARY KEY,
    conteudo BLOB NOT NULL
);
"""


def caminho_db() -> Path:
    return Path(os.environ.get("DB_PATH", "data/app.db"))


def usa_turso() -> bool:
    return bool(os.environ.get("TURSO_DATABASE_URL"))


class _Cursor:
    """Cursor do Turso com o comportamento do sqlite3 que o app usa (iterar)."""

    def __init__(self, cursor) -> None:
        self._c = cursor

    def __iter__(self):
        return iter(self._c.fetchall())

    def __getattr__(self, nome: str):
        return getattr(self._c, nome)


def _erro_sqlite(exc: Exception) -> sqlite3.Error:
    msg = str(exc)
    if "UNIQUE" in msg or "constraint" in msg.lower():
        return sqlite3.IntegrityError(msg)
    return sqlite3.OperationalError(msg)


class _ConexaoTurso:
    """Conexão do Turso com a interface do sqlite3 que o app usa: execute iterável,
    `with` que confirma ou desfaz, e os mesmos tipos de erro do sqlite3."""

    def __init__(self, con) -> None:
        self._c = con

    def execute(self, *args):
        try:
            return _Cursor(self._c.execute(*args))
        except ValueError as exc:
            raise _erro_sqlite(exc) from exc

    def executescript(self, script: str):
        try:
            return self._c.executescript(script)
        except ValueError as exc:
            raise _erro_sqlite(exc) from exc

    def __enter__(self):
        return self

    def __exit__(self, tipo, valor, tb) -> bool:
        if tipo is None:
            self._c.commit()
        else:
            self._c.rollback()
        return False

    def __getattr__(self, nome: str):
        return getattr(self._c, nome)


_esquema_pronto = False


def conectar() -> sqlite3.Connection:
    global _esquema_pronto
    if usa_turso():
        import libsql

        con = _ConexaoTurso(
            libsql.connect(
                # O painel do Turso dá libsql://; o acesso remoto é por HTTPS.
                database=os.environ["TURSO_DATABASE_URL"].replace(
                    "libsql://", "https://", 1
                ),
                auth_token=os.environ.get("TURSO_AUTH_TOKEN", ""),
            )
        )
        if not _esquema_pronto:  # cada comando é uma ida à rede: o esquema só uma vez
            con.executescript(_ESQUEMA)
            con.commit()
            _esquema_pronto = True
        return con  # type: ignore[return-value]
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


# --- arquivos no banco -----------------------------------------------------------------
# No Render grátis o disco some a cada reinício. Com o Turso, cada arquivo gravado pelo
# app (conta, proposta, PDF, SVG) também vai para o banco e volta ao disco na partida.


def espelhar_arquivo(caminho: Path | str) -> None:
    if not usa_turso():
        return
    p = Path(caminho)
    with conectar() as con:
        con.execute(
            "INSERT OR REPLACE INTO arquivos (caminho, conteudo) VALUES (?, ?)",
            (p.as_posix(), p.read_bytes()),
        )


def restaurar_arquivos() -> int:
    """Grava no disco os arquivos guardados no banco que não estão lá. Devolve quantos."""
    if not usa_turso():
        return 0
    with conectar() as con:
        linhas = con.execute("SELECT caminho, conteudo FROM arquivos").fetchall()
    n = 0
    for caminho, conteudo in linhas:
        p = Path(caminho)
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(bytes(conteudo))
            n += 1
    return n
