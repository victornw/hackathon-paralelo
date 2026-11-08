from datetime import datetime

import pytest

from app.schemas import PassoTrace
from app.tracing.trace import gravar_passo
from evals import run


def _passo(pid, passo, ti=0, to=0, ms=0, custo=0.0, erro=None):
    return PassoTrace(
        processo_id=pid,
        passo=passo,
        tokens_entrada=ti,
        tokens_saida=to,
        ms=ms,
        custo_brl=custo,
        erro=erro,
        em=datetime(2026, 1, 1),
    )


@pytest.fixture
def db(tmp_path, monkeypatch):
    caminho = tmp_path / "trace.db"
    monkeypatch.setenv("DB_PATH", str(caminho))
    return caminho


@pytest.fixture(autouse=True)
def sem_llm(monkeypatch):
    monkeypatch.setattr("app.core.llm.disponivel", lambda *a, **k: False)


def test_custo_com_dados(db, tmp_path):
    gravar_passo(_passo("p1", "extrair", 100, 50, 2000, 0.10))
    gravar_passo(_passo("p1", "decidir", 200, 150, 4000, 0.20, erro="falhou"))
    gravar_passo(_passo("p2", "conferir", ms=999))
    gravar_passo(_passo("demo-01", "x", 9999, 9999, 99999, 9.0))
    gravar_passo(_passo("sem_processo", "y", 9999, 9999, 99999, 9.0))
    texto = run.montar(db, None)
    assert "| Tokens por processo (média) | 500 | 1 processo com LLM |" in texto
    assert "| Tempo por processo (média) | 6,0 s |" in texto
    assert "| Custo por processo (média) | R$ 0,30 |" in texto
    assert "| Passos com erro | 50,0% | 2 passos | 1 de 2 passos |" in texto
    assert "abaixo das 5 execuções previstas" in texto


def test_banco_vazio(db):
    assert (
        "| Custo por processo | não medido | — | nenhuma execução com LLM no trace |"
        in run.montar(db, None)
    )


def test_banco_inexistente(tmp_path):
    texto = run.montar(tmp_path / "nao-existe.db", None)
    assert "nenhuma execução com LLM no trace" in texto
    assert not (tmp_path / "nao-existe.db").exists()


def test_aneel(db, tmp_path):
    assert "base ANEEL não encontrada" in run.montar(db, None)
    assert "base ANEEL não encontrada" in run.montar(db, tmp_path / "nada.csv")
    arq = tmp_path / "aneel.csv"
    arq.write_text("a,b\n1,2\n")
    texto = run.montar(db, arq)
    assert "colunas ausentes na base" in texto
    assert "base ANEEL não encontrada" not in texto


def test_pendencias_presente(db):
    texto = run.montar(db, None)
    assert "Pendências: acerto geral (produto)" in texto
    assert "LLM não configurado" in texto
    assert "textos sintéticos, rotulados antes de rodar o modelo" in texto
    assert "Gerado em" in texto


def test_arquivo_igual_ao_impresso(db, tmp_path, capsys):
    saida = tmp_path / "out.md"
    run.main(["--db", str(db), "--saida", str(saida)])
    assert saida.read_text(encoding="utf-8") == capsys.readouterr().out
