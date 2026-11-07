"""Testes do cliente LLM com um cliente falso: nenhuma chamada de rede."""

from types import SimpleNamespace

import httpx
import openai
import pytest
from pydantic import BaseModel

from app.core import llm
from app.core.llm import LLMErro, LLMIndisponivel
from app.tracing import listar_passos, processo_atual, trace


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.setenv("RELOGIO_INICIO", "2026-11-13")
    monkeypatch.setenv("FEATHERLESS_API_KEY", "chave-de-teste")
    monkeypatch.setenv("MODELO_EXTRACAO", "modelo-extracao")
    monkeypatch.setenv("MODELO_VISAO", "modelo-visao")
    for nome in (
        "MODELO_PRINCIPAL",
        "MODELO_FALLBACK",
        "MODELO_DECISAO",
        "MODELO_REDACAO",
        "MODELO_PENDENCIA",
        "FEATHERLESS_BASE_URL",
    ):
        monkeypatch.delenv(nome, raising=False)


class Resposta(BaseModel):
    nome: str
    idade: int


class ClienteFalso:
    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.chamadas: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._criar))

    def _criar(self, **kwargs):
        self.chamadas.append({**kwargs, "messages": list(kwargs["messages"])})
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=resposta))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        )


@pytest.fixture
def falso(monkeypatch):
    def instalar(*respostas):
        cliente = ClienteFalso(*respostas)
        monkeypatch.setattr(llm, "_cliente", lambda: cliente)
        return cliente

    return instalar


def test_disponivel_exige_chave_e_modelo_do_papel(monkeypatch):
    assert llm.disponivel("extracao")
    assert not llm.disponivel("decisao")
    monkeypatch.delenv("FEATHERLESS_API_KEY")
    assert not llm.disponivel("extracao")


def test_cliente_usa_url_padrao_sem_retentativas_do_sdk():
    cliente = llm._cliente()
    assert str(cliente.base_url).startswith("https://api.featherless.ai/v1")
    assert cliente.max_retries == 0
    assert cliente.timeout == 60


def test_cliente_respeita_base_url_do_ambiente(monkeypatch):
    monkeypatch.setenv("FEATHERLESS_BASE_URL", "http://localhost:9999/v1")
    assert str(llm._cliente().base_url).startswith("http://localhost:9999/v1")


def test_cliente_sem_chave_levanta_indisponivel(monkeypatch):
    monkeypatch.delenv("FEATHERLESS_API_KEY")
    with pytest.raises(LLMIndisponivel):
        llm._cliente()


def test_papel_sem_modelo_levanta_indisponivel(falso):
    falso('{"nome": "a", "idade": 1}')
    with pytest.raises(LLMIndisponivel):
        llm.completar_json("decisao", "s", "u", Resposta)


def test_json_com_texto_ao_redor_e_chaves_em_string(falso):
    cliente = falso('Claro!\n```json\n{"nome": "Ana {x}", "idade": 30}\n```\nPronto.')
    r = llm.completar_json("extracao", "sistema", "usuario", Resposta)
    assert r == Resposta(nome="Ana {x}", idade=30)
    assert cliente.chamadas[0]["model"] == "modelo-extracao"
    assert '"idade"' in cliente.chamadas[0]["messages"][0]["content"]


def test_um_reparo_citando_o_erro_de_validacao(falso):
    cliente = falso('{"nome": "Ana"}', '{"nome": "Ana", "idade": 30}')
    r = llm.completar_json("extracao", "s", "u", Resposta)
    assert r.idade == 30
    assert len(cliente.chamadas) == 2
    pedido_reparo = cliente.chamadas[1]["messages"][-1]["content"]
    assert "idade" in pedido_reparo


def test_resposta_sem_json_tambem_tem_reparo(falso):
    cliente = falso("não sei", '{"nome": "Ana", "idade": 30}')
    assert llm.completar_json("extracao", "s", "u", Resposta).nome == "Ana"
    assert len(cliente.chamadas) == 2


def test_falha_depois_do_reparo_levanta_llmerro(falso):
    cliente = falso('{"nome": "Ana"}', '{"nome": "Ana"}')
    with pytest.raises(LLMErro):
        llm.completar_json("extracao", "s", "u", Resposta)
    assert len(cliente.chamadas) == 2


def test_erro_da_api_vira_llmerro(falso):
    falso(openai.APIConnectionError(request=httpx.Request("POST", "http://x")))
    with pytest.raises(LLMErro):
        llm.completar_json("extracao", "s", "u", Resposta)


def test_imagens_vao_como_data_url_com_o_mime_certo(falso):
    cliente = falso('{"nome": "Ana", "idade": 30}')
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 8
    llm.completar_json("visao", "s", "u", Resposta, imagens=[png])
    conteudo = cliente.chamadas[0]["messages"][1]["content"]
    assert conteudo[0] == {"type": "text", "text": "u"}
    assert conteudo[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_completar_texto(falso):
    falso("  Olá!  ")
    assert llm.completar_texto("extracao", "s", "u") == "Olá!"


def test_tokens_de_todas_as_chamadas_do_passo_somam_no_trace(falso):
    falso('{"nome": "Ana"}', '{"nome": "Ana", "idade": 30}')

    @trace("passo_teste")
    def passo():
        return llm.completar_json("extracao", "s", "u", Resposta)

    with processo_atual("proc-1"):
        passo()
    (registro,) = listar_passos("proc-1")
    assert (registro.tokens_entrada, registro.tokens_saida) == (20, 10)


def test_principal_serve_todos_os_papeis_menos_visao(monkeypatch):
    monkeypatch.delenv("MODELO_EXTRACAO")
    monkeypatch.delenv("MODELO_VISAO")
    monkeypatch.setenv("MODELO_PRINCIPAL", "principal")
    assert llm.disponivel("decisao") and llm.disponivel("extracao")
    assert not llm.disponivel("visao")


def test_fallback_entra_quando_o_principal_falha_na_api(monkeypatch, falso):
    monkeypatch.delenv("MODELO_EXTRACAO")
    monkeypatch.setenv("MODELO_PRINCIPAL", "principal")
    monkeypatch.setenv("MODELO_FALLBACK", "reserva")
    erro = openai.APIConnectionError(request=httpx.Request("POST", "http://x"))
    cliente = falso(erro, '{"nome": "Ana", "idade": 30}')
    assert llm.completar_json("decisao", "s", "u", Resposta).nome == "Ana"
    assert [c["model"] for c in cliente.chamadas] == ["principal", "reserva"]


def test_fallback_entra_quando_o_principal_erra_o_esquema_apos_reparo(
    monkeypatch, falso
):
    monkeypatch.delenv("MODELO_EXTRACAO")
    monkeypatch.setenv("MODELO_PRINCIPAL", "principal")
    monkeypatch.setenv("MODELO_FALLBACK", "reserva")
    cliente = falso("nada", "ainda nada", '{"nome": "Bia", "idade": 9}')
    assert llm.completar_json("pendencia", "s", "u", Resposta).nome == "Bia"
    assert [c["model"] for c in cliente.chamadas] == [
        "principal",
        "principal",
        "reserva",
    ]


def test_sem_fallback_o_erro_do_principal_sobe(monkeypatch, falso):
    monkeypatch.delenv("MODELO_EXTRACAO")
    monkeypatch.setenv("MODELO_PRINCIPAL", "principal")
    falso("nada", "ainda nada")
    with pytest.raises(LLMErro, match="principal"):
        llm.completar_json("decisao", "s", "u", Resposta)
