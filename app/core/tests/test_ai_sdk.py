import pytest
from pydantic import BaseModel

from app.core import ai_sdk, llm
from app.tracing import listar_passos, processo_atual, trace


def test_python_node_generate_text_e_tracing(provider_sdk_local):
    class Resposta(BaseModel):
        nome: str
        idade: int

    @trace("extracao_sdk")
    def extrair():
        return llm.completar_json("extracao", "Leia", "Documento", Resposta)

    with processo_atual("sdk-local"):
        assert extrair().nome == "Ana"
    assert len(provider_sdk_local) == 1
    assert provider_sdk_local[0]["model"] == "local"
    (uso,) = listar_passos("sdk-local")
    assert (uso.tokens_entrada, uso.tokens_saida) == (10, 5)


def test_node_encerrado_sem_resposta_e_erro_explicito(monkeypatch, tmp_path):
    worker = tmp_path / "exit.mjs"
    worker.write_text("process.exit(1)")
    monkeypatch.setattr(ai_sdk, "WORKER", worker)
    with pytest.raises(ai_sdk.SDKError, match="encerrou sem resultado"):
        ai_sdk.run({"mode": "complete"})
