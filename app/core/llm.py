"""Cliente do LLM via Vercel AI SDK (Featherless).

Todo papel usa MODELO_PRINCIPAL, e MODELO_FALLBACK entra quando o principal
falha (erro de API ou resposta fora do esquema mesmo após o reparo). Um papel
pode sobrescrever o principal com MODELO_<PAPEL>. Visão só roda com
MODELO_VISAO explícito, porque nem todo modelo de texto lê imagem.
Não usamos response_format:
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

from pydantic import BaseModel, ValidationError

from app.core import ai_sdk
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


def _modelos(papel: Papel) -> list[str]:
    """Modelos a tentar, em ordem, sem repetição."""
    proprio = os.environ.get(_VAR_MODELO[papel])
    if papel == "visao":
        candidatos = [proprio]
    else:
        candidatos = [
            proprio or os.environ.get("MODELO_PRINCIPAL"),
            os.environ.get("MODELO_FALLBACK"),
        ]
    return list(dict.fromkeys(m for m in candidatos if m))


def disponivel(papel: Papel) -> bool:
    return bool(os.environ.get("FEATHERLESS_API_KEY")) and bool(_modelos(papel))


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


def _modelos_ou_erro(papel: Papel) -> list[str]:
    modelos = _modelos(papel)
    if not modelos:
        raise LLMIndisponivel(f"MODELO_PRINCIPAL ou {_VAR_MODELO[papel]} não definida")
    return modelos


def _com_fallback(papel: Papel, tentar):
    erros: list[str] = []
    for modelo in _modelos_ou_erro(papel):
        try:
            return tentar(modelo)
        except LLMErro as erro:
            erros.append(f"{modelo}: {erro}")
    raise LLMErro(" | ".join(erros))


def _chamar(modelo: str, mensagens: list[dict]) -> str:
    if not os.environ.get("FEATHERLESS_API_KEY"):
        raise LLMIndisponivel("FEATHERLESS_API_KEY não definida")
    try:
        resposta = ai_sdk.run(
            {"mode": "complete", "model": modelo, "messages": mensagens}
        )
    except ai_sdk.SDKError as exc:
        raise LLMErro(str(exc)) from exc
    registrar_uso(resposta.get("inputTokens", 0), resposta.get("outputTokens", 0))
    if not resposta.get("text"):
        raise LLMErro("resposta vazia do modelo")
    return resposta["text"]


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
        f"sem texto antes ou depois, sem explicação e sem mostrar raciocínio:\n{schema}\n/no_think"
    )
    inicio: list[dict] = [
        {"role": "system", "content": instrucao},
        {"role": "user", "content": _conteudo_usuario(usuario, imagens)},
    ]

    def tentar(modelo: str) -> T:
        resposta = _chamar(modelo, inicio)
        try:
            return _validar(resposta, esquema)
        except (ValueError, ValidationError) as erro:
            reparo = inicio + [
                {"role": "assistant", "content": resposta},
                {
                    "role": "user",
                    "content": f"A resposta não é válida: {erro}\nCorrija e responda só com o objeto JSON.",
                },
            ]
        resposta = _chamar(modelo, reparo)
        try:
            return _validar(resposta, esquema)
        except (ValueError, ValidationError) as erro:
            raise LLMErro(f"resposta fora do esquema após reparo: {erro}") from erro

    return _com_fallback(papel, tentar)


def completar_texto(papel: Papel, sistema: str, usuario: str) -> str:
    mensagens = [
        {"role": "system", "content": sistema},
        {"role": "user", "content": usuario},
    ]
    return _com_fallback(papel, lambda modelo: _chamar(modelo, mensagens).strip())
