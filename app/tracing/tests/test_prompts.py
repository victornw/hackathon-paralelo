import sqlite3

import pytest

from app.schemas import PassoTrace
from app.tracing import (
    carregar_prompt,
    listar_passos,
    listar_passos_detalhados,
    listar_prompts,
    processo_atual,
    registrar_uso,
    trace,
)
from app.tracing import prompts as modulo
from app.tracing.db import conectar


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    monkeypatch.setattr(modulo, "PASTA_PROMPTS", tmp_path)
    return tmp_path


def _escrever(pasta, nome, conteudo):
    (pasta / f"{nome}.md").write_text(conteudo, encoding="utf-8")


def test_carrega_versao_e_hash(pasta):
    _escrever(pasta, "p", "---\nversao: 3\ndescricao: x\n---\nOlá mundo\n")
    p = carregar_prompt("p")
    assert (p.nome, p.versao, p.texto) == ("p", 3, "Olá mundo")
    assert len(p.hash) == 8


def test_hash_muda_com_o_texto(pasta):
    _escrever(pasta, "p", "---\nversao: 1\n---\nA")
    h1 = carregar_prompt("p").hash
    _escrever(pasta, "p", "---\nversao: 1\n---\nB")
    assert carregar_prompt("p").hash != h1


def test_arquivo_ausente(pasta):
    with pytest.raises(KeyError, match="não encontrado"):
        carregar_prompt("nao_existe")


@pytest.mark.parametrize(
    "conteudo",
    ["sem cabecalho", "---\ndescricao: x\n---\ntexto", "---\nversao: abc\n---\ntexto"],
)
def test_cabecalho_invalido(pasta, conteudo):
    _escrever(pasta, "p", conteudo)
    with pytest.raises(ValueError):
        carregar_prompt("p")


def test_listar_prompts_reais():
    nomes = [p.nome for p in listar_prompts()]
    assert "classificar_pendencia" in nomes


def test_prompt_registrado_uma_vez_por_passo(pasta):
    _escrever(pasta, "p", "---\nversao: 2\n---\ntexto")
    prompt = carregar_prompt("p")

    @trace("passo_com_prompt")
    def com():
        registrar_uso(prompt=prompt)
        registrar_uso(prompt=prompt, decisao="ok")

    @trace("passo_sem_prompt")
    def sem():
        registrar_uso(decisao="ok")

    with processo_atual("proc-x"):
        com()
        sem()
    det = listar_passos_detalhados("proc-x")
    assert det[0].prompts == [f"p@v2#{prompt.hash}"]
    assert det[1].prompts == []
    assert [p.passo for p in listar_passos("proc-x")] == [
        "passo_com_prompt",
        "passo_sem_prompt",
    ]
    assert isinstance(det[0].passo, PassoTrace)


def test_banco_antigo_e_migrado(tmp_path, monkeypatch):
    caminho = tmp_path / "antigo.db"
    monkeypatch.setenv("DB_PATH", str(caminho))
    con = sqlite3.connect(caminho)
    con.execute(
        "CREATE TABLE passos_trace (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "processo_id TEXT NOT NULL, json TEXT NOT NULL)"
    )
    con.commit()
    con.close()
    with conectar() as nova:
        colunas = [
            linha[1] for linha in nova.execute("PRAGMA table_info(passos_trace)")
        ]
    assert "prompts" in colunas
    assert listar_passos_detalhados("qualquer") == []
