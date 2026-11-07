from collections import Counter

import pytest

from app.portal_sim.pendencias import CATEGORIAS, _normalizar
from evals import pendencias as ev


@pytest.fixture(scope="module")
def dados():
    return ev.carregar()


def test_carrega_e_valida(dados):
    assert len(dados) == 48
    assert len({d["id"] for d in dados}) == 48


def test_seis_por_categoria(dados):
    contagem = Counter(d["categoria"] for d in dados)
    assert set(contagem) == set(CATEGORIAS)
    assert all(n == 6 for n in contagem.values())


def test_parafrases_sem_palavras_chave(dados):
    for cat, info in CATEGORIAS.items():
        paras = [d for d in dados if d["categoria"] == cat and d["parafrase"]]
        if cat == "outros":  # sem palavras-chave: paráfrase não se aplica
            assert paras == []
            continue
        assert len(paras) >= 3, cat
        for d in paras:
            t = _normalizar(d["texto"])
            achadas = [p for p in info["palavras"] if p in t]
            assert not achadas, (d["id"], achadas)


def test_carregar_rejeita_invalidos(tmp_path):
    f = tmp_path / "x.jsonl"
    f.write_text(
        '{"id":"a","texto":"x","categoria":"outros"}\n'
        '{"id":"a","texto":"y","categoria":"outros"}\n'
    )
    with pytest.raises(ValueError):
        ev.carregar(f)
    f.write_text('{"id":"a","texto":"x","categoria":"nada"}\n')
    with pytest.raises(ValueError):
        ev.carregar(f)
    f.write_text('{"id":"a","texto":"  ","categoria":"outros"}\n')
    with pytest.raises(ValueError):
        ev.carregar(f)


def test_avaliar_dataset_pequeno():
    dados = [
        {"id": "1", "texto": "a", "categoria": "outros", "parafrase": True},
        {"id": "2", "texto": "b", "categoria": "localizacao", "parafrase": False},
        {"id": "3", "texto": "c", "categoria": "localizacao", "parafrase": True},
        {"id": "4", "texto": "d", "categoria": "outros", "parafrase": False},
    ]
    saida = {"a": "outros", "b": "localizacao", "c": "outros", "d": "padrao_entrada"}
    r = ev.avaliar(lambda t: saida[t], dados)
    assert r["n"] == 4
    assert r["acerto_geral"] == 0.5
    assert r["acerto_parafrase"] == 0.5
    assert r["acerto_por_categoria"] == {"localizacao": 0.5, "outros": 0.5}
    assert {e["id"] for e in r["erros"]} == {"3", "4"}
    assert r["erros"][0] == {"id": "3", "esperado": "localizacao", "obtido": "outros"}


def test_tabela_markdown():
    r = {"acerto_geral": 0.5, "acerto_parafrase": 0.25, "n": 4}
    tabela = ev.tabela_markdown({"X": r})
    assert (
        tabela.splitlines()[0] == "| Método | Acerto geral | Acerto em paráfrases | n |"
    )
    assert "| X | 50.0% | 25.0% | 4 |" in tabela


def test_executar_sem_llm(monkeypatch, tmp_path, dados):
    monkeypatch.setattr("app.core.llm.disponivel", lambda papel: False)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "eval.db"))
    resultados, llm_ok = ev.executar(dados)
    assert llm_ok is False
    nomes = list(resultados)
    assert "LLM não configurado: classificador = palavras-chave" in nomes[-1]
    assert resultados[nomes[-1]]["acerto_geral"] == resultados[nomes[1]]["acerto_geral"]
