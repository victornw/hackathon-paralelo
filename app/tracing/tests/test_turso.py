"""Banco local espelhado no Turso, com o cliente libsql sobre um arquivo local (sem rede)."""

import sqlite3

import pytest

from app.tracing import db


@pytest.fixture
def turso(tmp_path, monkeypatch):
    monkeypatch.setenv("TURSO_DATABASE_URL", str(tmp_path / "turso.db"))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "local.db"))
    monkeypatch.setattr(db, "_copiado_do_turso", False)
    monkeypatch.setattr(db, "_fila", None)
    monkeypatch.setattr(db, "_scripts_replicados", set())
    return tmp_path


def _no_turso(tmp_path, sql: str) -> list[tuple]:
    db.aguardar_replicacao()
    con = sqlite3.connect(tmp_path / "turso.db")
    try:
        return [tuple(r) for r in con.execute(sql)]
    finally:
        con.close()


def test_gravacao_confirmada_chega_ao_turso(turso):
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
    assert _no_turso(turso, "SELECT id, data FROM relogio") == [(1, "2026-11-08")]


def test_gravacao_desfeita_nao_vai_ao_turso(turso):
    with pytest.raises(RuntimeError), db.conectar() as con:
        con.execute("INSERT INTO relogio (id, data) VALUES (1, '2026-11-08')")
        raise RuntimeError
    con = db.conectar()
    con.execute("INSERT INTO relogio (id, data) VALUES (1, '2026-11-09')")
    con.close()
    assert _no_turso(turso, "SELECT data FROM relogio") == []
    assert list(db.conectar().execute("SELECT data FROM relogio")) == []


def test_partida_copia_o_turso_para_o_banco_local(turso, monkeypatch):
    remoto = sqlite3.connect(turso / "turso.db")
    remoto.executescript(db._ESQUEMA)
    remoto.execute("INSERT INTO relogio (id, data) VALUES (1, '2026-12-01')")
    remoto.execute(
        "INSERT INTO passos_trace (processo_id, json) VALUES ('p1', '{}'), ('p1', '{}')"
    )
    remoto.commit()
    remoto.close()
    local = sqlite3.connect(turso / "local.db")
    local.executescript(db._ESQUEMA)
    local.execute("INSERT INTO relogio (id, data) VALUES (1, '2020-01-01')")
    local.commit()
    local.close()
    with db.conectar() as con:
        assert list(con.execute("SELECT data FROM relogio")) == [("2026-12-01",)]
        con.execute("INSERT INTO passos_trace (processo_id, json) VALUES ('p1', '{}')")
    assert _no_turso(turso, "SELECT id FROM passos_trace ORDER BY id") == [
        (1,),
        (2,),
        (3,),
    ]


def test_arquivo_espelhado_volta_ao_disco(turso):
    arquivo = turso / "docs" / "proc-1" / "memorial.pdf"
    arquivo.parent.mkdir(parents=True)
    arquivo.write_bytes(b"%PDF-1.4 conteudo")
    db.espelhar_arquivo(arquivo)
    arquivo.unlink()
    assert db.restaurar_arquivos() == 1
    assert arquivo.read_bytes() == b"%PDF-1.4 conteudo"
    assert db.restaurar_arquivos() == 0  # o que já está no disco fica como está
    assert len(_no_turso(turso, "SELECT caminho FROM arquivos")) == 1


def test_sem_turso_nada_muda(tmp_path, monkeypatch):
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    arquivo = tmp_path / "a.pdf"
    arquivo.write_bytes(b"x")
    db.espelhar_arquivo(arquivo)
    assert db.restaurar_arquivos() == 0
    assert isinstance(db.conectar(), sqlite3.Connection)
