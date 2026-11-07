"""Cliente do LLM (Featherless, compatível com a API da OpenAI).

O modelo de cada papel vem do ambiente (MODELO_EXTRACAO, MODELO_VISAO,
MODELO_DECISAO, MODELO_REDACAO, MODELO_PENDENCIA). Não usamos response_format:
o esquema JSON vai no prompt, o primeiro objeto JSON da resposta é validado
com Pydantic e há uma tentativa de reparo citando o erro. A política de
retentativa de falhas de rede fica no orquestrador (max_retries=0 aqui).
"""

from __future__ import annotations

import base64
import json
import os
from collections.abc import Sequence
from typing import Literal, TypeVar

import openai
from pydantic import BaseModel, ValidationError

from app.tracing import registrar_uso

Papel = Literal["extracao", "visao", "decisao", "redacao", "pendencia"]
T = TypeVar("T", bound=BaseModel)

URL_PADRAO = "https://api.featherless.ai/v1"
TIMEOUT_S = 60.0
_VAR_MODELO: dict[str, str] = {
    "extracao": "MODELO_EXTRACAO",
    "visao": "MODELO_VISAO",
    "decisao": "MODELO_DECISAO",
    "redacao": "MODELO_REDACAO",
    "pendencia": "MODELO_PENDENCIA",
}
_ASSINATURAS_IMAGEM = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"RIFF": "image/webp",
}


class LLMIndisponivel(Exception):
    """Falta chave ou modelo para o papel pedido."""


class LLMErro(Exception):
    """A chamada falhou ou a resposta não passou na validação."""


def _modelo(papel: Papel) -> str | None:
    return os.environ.get(_VAR_MODELO[papel]) or None


def disponivel(papel: Papel) -> bool:
    return bool(os.environ.get("FEATHERLESS_API_KEY")) and _modelo(papel) is not None


def _cliente() -> openai.OpenAI:
    chave = os.environ.get("FEATHERLESS_API_KEY")
    if not chave:
        raise LLMIndisponivel("FEATHERLESS_API_KEY não definida")
    return openai.OpenAI(
        api_key=chave,
        base_url=os.environ.get("FEATHERLESS_BASE_URL") or URL_PADRAO,
        timeout=TIMEOUT_S,
        max_retries=0,
    )


def _data_url(imagem: bytes) -> str:
    mime = next(
        (m for ass, m in _ASSINATURAS_IMAGEM.items() if imagem.startswith(ass)),
        "image/jpeg",
    )
    return f"data:{mime};base64,{base64.b64encode(imagem).decode()}"


def _conteudo_usuario(texto: str, imagens: Sequence[bytes]) -> str | list[dict]:
    if not imagens:
        return texto
    partes: list[dict] = [{"type": "text", "text": texto}]
    partes += [
        {"type": "image_url", "image_url": {"url": _data_url(i)}} for i in imagens
    ]
    return partes


def _chamar(papel: Papel, mensagens: list[dict]) -> str:
    modelo = _modelo(papel)
    if modelo is None:
        raise LLMIndisponivel(f"{_VAR_MODELO[papel]} não definida")
    cliente = _cliente()
    try:
        resposta = cliente.chat.completions.create(model=modelo, messages=mensagens)
    except openai.OpenAIError as exc:
        raise LLMErro(f"{type(exc).__name__}: {exc}") from exc
    uso = getattr(resposta, "usage", None)
    registrar_uso(
        getattr(uso, "prompt_tokens", 0) or 0,
        getattr(uso, "completion_tokens", 0) or 0,
    )
    if not resposta.choices or not resposta.choices[0].message.content:
        raise LLMErro("resposta vazia do modelo")
    return resposta.choices[0].message.content


def _primeiro_objeto_json(texto: str) -> str | None:
    """Primeiro objeto {...} balanceado do texto, ignorando chaves dentro de strings."""
    inicio = texto.find("{")
    while inicio != -1:
        profundidade, em_string, escapado = 0, False, False
        for i in range(inicio, len(texto)):
            c = texto[i]
            if em_string:
                escapado = (c == "\\") and not escapado
                if c == '"' and not escapado:
                    em_string = False
                continue
            if c == '"':
                em_string = True
            elif c == "{":
                profundidade += 1
            elif c == "}":
                profundidade -= 1
                if profundidade == 0:
                    return texto[inicio : i + 1]
        inicio = texto.find("{", inicio + 1)
    return None


def _validar(texto: str, esquema: type[T]) -> T:
    bruto = _primeiro_objeto_json(texto)
    if bruto is None:
        raise ValueError("a resposta não contém um objeto JSON")
    return esquema.model_validate(json.loads(bruto))


def completar_json(
    papel: Papel,
    sistema: str,
    usuario: str,
    esquema: type[T],
    imagens: Sequence[bytes] = (),
) -> T:
    schema = json.dumps(esquema.model_json_schema(), ensure_ascii=False)
    instrucao = (
        f"{sistema}\n\nResponda SOMENTE com um objeto JSON que siga este esquema, "
        f"sem texto antes ou depois:\n{schema}"
    )
    mensagens: list[dict] = [
        {"role": "system", "content": instrucao},
        {"role": "user", "content": _conteudo_usuario(usuario, imagens)},
    ]
    resposta = _chamar(papel, mensagens)
    try:
        return _validar(resposta, esquema)
    except (ValueError, ValidationError) as erro:
        mensagens += [
            {"role": "assistant", "content": resposta},
            {
                "role": "user",
                "content": f"A resposta não é válida: {erro}\nCorrija e responda só com o objeto JSON.",
            },
        ]
    resposta = _chamar(papel, mensagens)
    try:
        return _validar(resposta, esquema)
    except (ValueError, ValidationError) as erro:
        raise LLMErro(f"resposta fora do esquema após reparo: {erro}") from erro


def completar_texto(papel: Papel, sistema: str, usuario: str) -> str:
    return _chamar(
        papel,
        [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
    ).strip()
