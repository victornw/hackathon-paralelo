"""Prompts versionados: arquivos .md em prompts_txt/ com cabeçalho mínimo.

    ---
    versao: 1
    descricao: uma linha
    ---
    <texto do prompt>

O hash (8 primeiros hex do sha256 do texto) identifica o conteúdo exato usado;
o rastreio grava `nome@vN#hash` em cada passo que usou o prompt.
A pasta se chama prompts_txt (e não prompts) para não colidir com este módulo.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

PASTA_PROMPTS = Path(__file__).parent / "prompts_txt"


@dataclass(frozen=True)
class Prompt:
    nome: str
    versao: int
    texto: str
    hash: str


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:8]


def _ler(caminho: Path) -> Prompt:
    bruto = caminho.read_text(encoding="utf-8")
    partes = bruto.split("---", 2)
    if not bruto.startswith("---") or len(partes) < 3:
        raise ValueError(
            f"Prompt '{caminho.stem}': cabeçalho '---' ausente ou incompleto."
        )
    cabecalho: dict[str, str] = {}
    for linha in partes[1].strip().splitlines():
        chave, sep, valor = linha.partition(":")
        if sep:
            cabecalho[chave.strip()] = valor.strip()
    try:
        versao = int(cabecalho["versao"])
    except (KeyError, ValueError):
        raise ValueError(
            f"Prompt '{caminho.stem}': 'versao' ausente ou não inteira."
        ) from None
    if versao < 1:
        raise ValueError(f"Prompt '{caminho.stem}': 'versao' deve ser >= 1.")
    texto = partes[2].strip()
    return Prompt(nome=caminho.stem, versao=versao, texto=texto, hash=_hash(texto))


def carregar_prompt(nome: str) -> Prompt:
    caminho = PASTA_PROMPTS / f"{nome}.md"
    if not caminho.is_file():
        raise KeyError(f"Prompt '{nome}' não encontrado em {PASTA_PROMPTS}.")
    return _ler(caminho)


def listar_prompts() -> list[Prompt]:
    return [_ler(c) for c in sorted(PASTA_PROMPTS.glob("*.md"))]
