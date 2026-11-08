"""Persistência: processos, arquivos enviados e memória do orquestrador.

Os processos ficam na tabela `processos(id, json)` do SQLite (a mesma que o
painel lê). Quem muda um processo existente usa `atualizar`, que serializa as
escritas por processo: a API e o orquestrador (em outra thread) nunca se
sobrescrevem.

Os uploads ficam em UPLOADS_DIR (padrão data/uploads)/<id>/<tipo>/<arquivo>.
A tabela `orquestrador_memoria` guarda, por processo e passo, o hash das
entradas já tratadas; é o que torna o orquestrador idempotente.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.portal_sim.relogio import hoje
from app.schemas import Processo
from app.tracing.db import conectar

TIPOS_ARQUIVO = ("conta", "proposta", "datasheet", "padrao")

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS processos (
    id TEXT PRIMARY KEY,
    json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orquestrador_memoria (
    processo_id TEXT NOT NULL,
    passo TEXT NOT NULL,
    hash TEXT NOT NULL,
    PRIMARY KEY (processo_id, passo)
);
"""

_trancas: dict[str, threading.RLock] = {}
_guarda = threading.Lock()


class ProcessoNaoEncontrado(KeyError):
    pass


@contextmanager
def _transacao() -> Iterator[sqlite3.Connection]:
    con = conectar()
    try:
        con.executescript(_ESQUEMA)
        with con:
            yield con
    finally:
        con.close()


def agora() -> datetime:
    """Data do relógio simulado com a hora real, como o resto do sistema."""
    return datetime.combine(hoje(), datetime.now().time())


def salvar(processo: Processo) -> None:
    with _transacao() as con:
        con.execute(
            "INSERT INTO processos (id, json) VALUES (?, ?) "
            "ON CONFLICT(id) DO UPDATE SET json = excluded.json",
            (processo.id, processo.model_dump_json()),
        )


def carregar(processo_id: str) -> Processo:
    with _transacao() as con:
        linha = con.execute(
            "SELECT json FROM processos WHERE id = ?", (processo_id,)
        ).fetchone()
    if linha is None:
        raise ProcessoNaoEncontrado(processo_id)
    return Processo.model_validate_json(linha[0])


def listar() -> list[Processo]:
    with _transacao() as con:
        linhas = con.execute("SELECT json FROM processos ORDER BY rowid").fetchall()
    return [Processo.model_validate_json(j) for (j,) in linhas]


def criar(email_contato: str | None = None) -> Processo:
    processo = Processo(
        id=f"proc-{uuid.uuid4().hex[:8]}",
        criado_em=agora(),
        email_contato=email_contato,
    )
    salvar(processo)
    return processo


def _tranca(processo_id: str) -> threading.RLock:
    with _guarda:
        return _trancas.setdefault(processo_id, threading.RLock())


def atualizar(processo_id: str, mudar: Callable[[Processo], None]) -> Processo:
    """Carrega, aplica `mudar` e salva sob a trava do processo. Se `mudar`
    levanta, nada é salvo."""
    with _tranca(processo_id):
        processo = carregar(processo_id)
        mudar(processo)
        salvar(processo)
        return processo


# --- uploads ---------------------------------------------------------------------


def pasta_uploads() -> Path:
    return Path(os.environ.get("UPLOADS_DIR", "data/uploads"))


def guardar_arquivo(processo_id: str, tipo: str, nome: str, conteudo: bytes) -> Path:
    if tipo not in TIPOS_ARQUIVO:
        raise ValueError(
            f"Tipo de arquivo inválido: {tipo}. Use: {', '.join(TIPOS_ARQUIVO)}."
        )
    nome_limpo = Path(nome).name
    if nome_limpo in ("", ".", ".."):
        raise ValueError("Nome de arquivo inválido.")
    destino = pasta_uploads() / processo_id / tipo / nome_limpo
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(conteudo)
    from app.tracing.db import espelhar_arquivo

    espelhar_arquivo(destino)  # com Turso, a conta enviada sobrevive ao reinício
    return destino


def arquivos(processo_id: str) -> dict[str, list[Path]]:
    raiz = pasta_uploads() / processo_id
    return {
        tipo: sorted(f for f in (raiz / tipo).glob("*") if f.is_file())
        for tipo in TIPOS_ARQUIVO
    }


# --- memória do orquestrador ---------------------------------------------------------


def memoria(processo_id: str) -> dict[str, str]:
    with _transacao() as con:
        linhas = con.execute(
            "SELECT passo, hash FROM orquestrador_memoria WHERE processo_id = ?",
            (processo_id,),
        ).fetchall()
    return dict(linhas)


def marcar(processo_id: str, passo: str, hash_entrada: str) -> None:
    with _transacao() as con:
        con.execute(
            "INSERT INTO orquestrador_memoria (processo_id, passo, hash) VALUES (?, ?, ?) "
            "ON CONFLICT(processo_id, passo) DO UPDATE SET hash = excluded.hash",
            (processo_id, passo, hash_entrada),
        )


def esquecer(processo_id: str, passo: str) -> None:
    with _transacao() as con:
        con.execute(
            "DELETE FROM orquestrador_memoria WHERE processo_id = ? AND passo = ?",
            (processo_id, passo),
        )
