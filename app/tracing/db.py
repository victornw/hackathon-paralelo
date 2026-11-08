"""Conexão com o banco, usada por todo o app (processos, portal, relógio, trace).

O app sempre lê e grava num SQLite local em DB_PATH (padrão: data/app.db); testes
apontam DB_PATH para um arquivo temporário. Com TURSO_DATABASE_URL e TURSO_AUTH_TOKEN,
o Turso (SQLite hospedado) guarda uma cópia durável: na primeira conexão o app copia
o Turso para o arquivo local, e cada gravação confirmada é repetida no Turso por uma
thread em segundo plano. Assim nenhuma página espera a rede, e os dados sobrevivem a
deploys e reinícios do Render grátis, que roda um único processo.
Os arquivos (contas enviadas, PDFs gerados) são espelhados na tabela `arquivos` e
restaurados no disco quando o app sobe (ver espelhar_arquivo / restaurar_arquivos).
"""

from __future__ import annotations

import logging
import os
import queue
import sqlite3
import threading
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

_log = logging.getLogger(__name__)


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


def _abrir_turso():
    import libsql

    return libsql.connect(
        database=os.environ["TURSO_DATABASE_URL"].replace("libsql://", "https://", 1),
        auth_token=os.environ.get("TURSO_AUTH_TOKEN", ""),
        isolation_level=None,
    )


def _expirou(exc: Exception) -> bool:
    msg = str(exc)
    return (
        "STREAM_EXPIRED" in msg or "stream was idle" in msg or "stream" in msg.lower()
    )


class _ConexaoTurso:
    """Conexão do Turso em autocommit, com os mesmos tipos de erro do sqlite3. Se o
    servidor encerrou a conexão por inatividade, reconecta e repete o comando."""

    def __init__(self, con) -> None:
        self._c = con

    def execute(self, *args):
        try:
            return _Cursor(self._c.execute(*args))
        except ValueError as exc:
            if _expirou(exc):
                self._c = _abrir_turso()
                try:
                    return _Cursor(self._c.execute(*args))
                except ValueError as exc2:
                    raise _erro_sqlite(exc2) from exc2
            raise _erro_sqlite(exc) from exc

    def executescript(self, script: str):
        try:
            return self._c.executescript(script)
        except ValueError as exc:
            raise _erro_sqlite(exc) from exc

    def close(self) -> None:
        try:
            self._c.close()
        except Exception:  # noqa: BLE001, S110 - conexão já encerrada pelo servidor
            pass


_trava = threading.Lock()
_copiado_do_turso = False
_fila: queue.Queue | None = None
_scripts_replicados: set[str] = set()


def _replicador(fila: queue.Queue) -> None:
    remoto: _ConexaoTurso | None = None
    while True:
        itens = fila.get()
        try:
            for tipo, sql, parametros in itens:
                try:
                    if remoto is None:
                        remoto = _ConexaoTurso(_abrir_turso())
                    if tipo == "script":
                        remoto.executescript(sql)
                    else:
                        remoto.execute(sql, parametros)
                except Exception:  # noqa: BLE001 - uma gravação perdida não para as outras
                    _log.exception("Não foi possível repetir no Turso: %s", sql[:80])
                    remoto = None
        finally:
            fila.task_done()


def _replicar(itens: list[tuple[str, str, tuple]]) -> None:
    global _fila
    if not itens:
        return
    with _trava:
        if _fila is None:
            _fila = queue.Queue()
            threading.Thread(
                target=_replicador, args=(_fila,), daemon=True, name="turso"
            ).start()
        _fila.put(itens)


def aguardar_replicacao() -> None:
    """Espera o Turso receber tudo o que já foi confirmado no banco local."""
    if _fila is not None:
        _fila.join()


def _altera(sql: str) -> bool:
    palavra = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ""
    return palavra not in ("SELECT", "PRAGMA", "EXPLAIN")


class _ConexaoEspelhada:
    """SQLite local que, a cada gravação confirmada, manda a mesma gravação ao
    Turso. Gravação desfeita (rollback, ou fechada sem commit) não sai daqui."""

    def __init__(self, con: sqlite3.Connection) -> None:
        self._c = con
        self._pendentes: list[tuple[str, str, tuple]] = []

    def _enviar(self) -> None:
        itens, self._pendentes = self._pendentes, []
        _replicar(itens)

    def execute(self, sql: str, parametros=()):
        cursor = self._c.execute(sql, parametros)
        if _altera(sql):
            copia = dict(parametros) if isinstance(parametros, dict) else tuple(parametros)
            self._pendentes.append(("sql", sql, copia))
            if not self._c.in_transaction:
                self._enviar()
        return cursor

    def executescript(self, script: str):
        resultado = self._c.executescript(script)
        if script not in _scripts_replicados:
            _scripts_replicados.add(script)
            _replicar([("script", script, ())])
        return resultado

    def commit(self) -> None:
        self._c.commit()
        self._enviar()

    def rollback(self) -> None:
        self._c.rollback()
        self._pendentes.clear()

    def close(self) -> None:
        self._c.close()
        self._pendentes.clear()

    def __enter__(self):
        self._c.__enter__()
        return self

    def __exit__(self, tipo, valor, tb) -> bool:
        resultado = self._c.__exit__(tipo, valor, tb)
        if tipo is None:
            self._enviar()
        else:
            self._pendentes.clear()
        return resultado

    def __getattr__(self, nome: str):
        return getattr(self._c, nome)


def _sqlite_local() -> sqlite3.Connection:
    caminho = caminho_db()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(caminho)
    con.executescript(_ESQUEMA)
    colunas = {linha[1] for linha in con.execute("PRAGMA table_info(passos_trace)")}
    if "prompts" not in colunas:
        con.execute(
            "ALTER TABLE passos_trace ADD COLUMN prompts TEXT NOT NULL DEFAULT '[]'"
        )
        con.commit()
    return con


def _copiar_do_turso() -> None:
    """Troca o conteúdo do banco local pelo do Turso, uma vez por processo."""
    global _copiado_do_turso
    with _trava:
        if _copiado_do_turso:
            return
        remoto = _ConexaoTurso(_abrir_turso())
        local = _sqlite_local()
        try:
            tabelas = remoto.execute(
                "SELECT name, sql FROM sqlite_master"
                " WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                " AND name NOT LIKE 'libsql_%' AND name NOT LIKE '_litestream%'"
            ).fetchall()
            for nome, sql in tabelas:
                linhas = remoto.execute(f'SELECT * FROM "{nome}"').fetchall()
                local.execute(f'DROP TABLE IF EXISTS "{nome}"')
                local.execute(sql)
                if linhas:
                    marcas = ", ".join("?" * len(linhas[0]))
                    local.executemany(
                        f'INSERT INTO "{nome}" VALUES ({marcas})',
                        [tuple(linha) for linha in linhas],
                    )
            local.commit()
        finally:
            local.close()
            remoto.close()
        _copiado_do_turso = True
        _log.info("Banco local copiado do Turso: %d tabelas.", len(tabelas))


def conectar() -> sqlite3.Connection:
    if not usa_turso():
        return _sqlite_local()
    if not _copiado_do_turso:
        _copiar_do_turso()
    con = _ConexaoEspelhada(_sqlite_local())
    if _ESQUEMA not in _scripts_replicados:
        _scripts_replicados.add(_ESQUEMA)
        _replicar([("script", _ESQUEMA, ())])
    return con  # type: ignore[return-value]


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
