"""O adaptador do Turso, rodando o cliente libsql sobre um arquivo local (sem rede)."""

import sqlite3

import pytest

from app.tracing import db


@pytest.fixture
def turso(tmp_path, monkeypatch):
    monkeypatch.setenv("TURSO_DATABASE_URL", str(tmp_path / "turso.db"))
    monkeypatch.setattr(db, "_esquema_pronto", False)
    return tmp_path


def test_conexao_turso_se_comporta_como_sqlite(turso):
    with db.conectar() as con:
        con.execute("INSERT INTO relogio (id, data) VALUES (1, '2026-11-08')")
    with db.conectar() as con:
        assert [tuple(r) for r in con.execute("SELECT id, data FROM relogio")] == [
            (1, "2026-11-08")
        ]
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("INSERT INTO relogio (id, data) VALUES (1, 'x')")
        with pytest.raises(sqlite3.OperationalError):
            con.execute("SELECT * FROM tabela_que_nao_existe")


def test_arquivo_espelhado_volta_ao_disco(turso):
    arquivo = turso / "docs" / "proc-1" / "memorial.pdf"
    arquivo.parent.mkdir(parents=True)
    arquivo.write_bytes(b"%PDF-1.4 conteudo")
    db.espelhar_arquivo(arquivo)
    arquivo.unlink()
    assert db.restaurar_arquivos() == 1
    assert arquivo.read_bytes() == b"%PDF-1.4 conteudo"
    assert db.restaurar_arquivos() == 0  # o que já está no disco fica como está


def test_sem_turso_nada_muda(tmp_path, monkeypatch):
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    arquivo = tmp_path / "a.pdf"
    arquivo.write_bytes(b"x")
    db.espelhar_arquivo(arquivo)
    assert db.restaurar_arquivos() == 0
    assert isinstance(db.conectar(), sqlite3.Connection)
