"""Tracing: cada chamada de LLM e cada ferramenta grava um PassoTrace no SQLite.

Uso:

    from app.tracing import trace, registrar_uso, processo_atual

    @trace("extrair_conta")
    def extrair_conta(arquivo): ...
        resposta = llm(...)
        registrar_uso(resposta.tokens_entrada, resposta.tokens_saida,
                      decisao="Conta lida; UC com confiança 0,95.")

    with processo_atual(processo.id):   # o orquestrador abre o contexto
        extrair_conta(arquivo)

O processo_id do passo vem, em ordem: do argumento `processo_id=` da chamada,
de um argumento que seja um Processo, ou do contexto aberto por processo_atual().

Custo: registrar_uso aceita custo_brl explícito; sem ele, o custo sai dos tokens
e dos preços do .env (LLM_PRECO_ENTRADA_USD_MTOK, LLM_PRECO_SAIDA_USD_MTOK,
USD_BRL). Sem preço configurado, o custo fica 0 — nunca um preço inventado.
"""

from __future__ import annotations

import functools
import json
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime

from app.schemas import PassoTrace, Processo
from app.tracing.db import conectar
from app.tracing.prompts import Prompt

SEM_PROCESSO = "sem_processo"

_processo: ContextVar[str | None] = ContextVar("processo_trace", default=None)
_uso: ContextVar[_Uso | None] = ContextVar("uso_trace", default=None)


@dataclass
class _Uso:
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_brl: float | None = None
    decisao: str | None = None
    prompts: list[str] = field(default_factory=list)


def _float_env(nome: str) -> float | None:
    valor = os.environ.get(nome)
    return float(valor) if valor else None


def custo_por_tokens(tokens_entrada: int, tokens_saida: int) -> float:
    """Custo em reais a partir dos preços por milhão de tokens do .env."""
    preco_in = _float_env("LLM_PRECO_ENTRADA_USD_MTOK")
    preco_out = _float_env("LLM_PRECO_SAIDA_USD_MTOK")
    cambio = _float_env("USD_BRL")
    if preco_in is None or preco_out is None or cambio is None:
        return 0.0
    usd = tokens_entrada / 1e6 * preco_in + tokens_saida / 1e6 * preco_out
    return round(usd * cambio, 6)


@contextmanager
def processo_atual(processo_id: str) -> Iterator[None]:
    token = _processo.set(processo_id)
    try:
        yield
    finally:
        _processo.reset(token)


def registrar_uso(
    tokens_entrada: int = 0,
    tokens_saida: int = 0,
    decisao: str | None = None,
    custo_brl: float | None = None,
    prompt: Prompt | None = None,
) -> None:
    """Chamado de dentro de uma função decorada com @trace. Acumula tokens e custo
    (várias chamadas de LLM no mesmo passo somam) e guarda a última decisão.
    `prompt` registra o prompt versionado usado (sem repetição, em ordem)."""
    uso = _uso.get()
    if uso is None:
        return  # fora de um @trace: nada a registrar
    uso.tokens_entrada += tokens_entrada
    uso.tokens_saida += tokens_saida
    if custo_brl is not None:
        uso.custo_brl = (uso.custo_brl or 0.0) + custo_brl
    if decisao is not None:
        uso.decisao = decisao
    if prompt is not None:
        ref = f"{prompt.nome}@v{prompt.versao}#{prompt.hash}"
        if ref not in uso.prompts:
            uso.prompts.append(ref)


def _agora() -> datetime:
    """Data do relógio simulado com a hora real, para ordenar a timeline."""
    from app.portal_sim.relogio import hoje  # import tardio: relogio usa tracing.db

    return datetime.combine(hoje(), datetime.now().time())


def _descobrir_processo(args: tuple, kwargs: dict) -> str:
    if isinstance(kwargs.get("processo_id"), str):
        return kwargs["processo_id"]
    for valor in (*args, *kwargs.values()):
        if isinstance(valor, Processo):
            return valor.id
    return _processo.get() or SEM_PROCESSO


def gravar_passo(passo: PassoTrace, prompts: list[str] | None = None) -> None:
    with conectar() as con:
        con.execute(
            "INSERT INTO passos_trace (processo_id, json, prompts) VALUES (?, ?, ?)",
            (passo.processo_id, passo.model_dump_json(), json.dumps(prompts or [])),
        )


def trace(nome_passo: str) -> Callable:
    """Decorador que grava um PassoTrace (tempo, tokens, custo, decisão, erro).
    Exceções são registradas e relançadas: o trace nunca engole erro."""

    def decorador(func: Callable) -> Callable:
        @functools.wraps(func)
        def envoltorio(*args, **kwargs):
            processo_id = _descobrir_processo(args, kwargs)
            uso = _Uso()
            token_uso = _uso.set(uso)
            token_proc = _processo.set(processo_id)
            inicio = time.perf_counter()
            erro: str | None = None
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                erro = f"{type(exc).__name__}: {exc}"
                raise
            finally:
                ms = int((time.perf_counter() - inicio) * 1000)
                _uso.reset(token_uso)
                _processo.reset(token_proc)
                custo = (
                    uso.custo_brl
                    if uso.custo_brl is not None
                    else custo_por_tokens(uso.tokens_entrada, uso.tokens_saida)
                )
                gravar_passo(
                    PassoTrace(
                        processo_id=processo_id,
                        passo=nome_passo,
                        decisao=uso.decisao,
                        tokens_entrada=uso.tokens_entrada,
                        tokens_saida=uso.tokens_saida,
                        ms=ms,
                        custo_brl=custo,
                        erro=erro,
                        em=_agora(),
                    ),
                    uso.prompts,
                )

        return envoltorio

    return decorador


def listar_passos(processo_id: str) -> list[PassoTrace]:
    """Passos do processo em ordem de gravação (a timeline)."""
    with conectar() as con:
        linhas = con.execute(
            "SELECT json FROM passos_trace WHERE processo_id = ? ORDER BY id",
            (processo_id,),
        ).fetchall()
    return [PassoTrace.model_validate_json(j) for (j,) in linhas]


@dataclass
class PassoDetalhado:
    passo: PassoTrace
    prompts: list[str]


def listar_passos_detalhados(processo_id: str) -> list[PassoDetalhado]:
    """Como listar_passos, com os prompts (`nome@vN#hash`) que cada passo usou."""
    with conectar() as con:
        linhas = con.execute(
            "SELECT json, prompts FROM passos_trace WHERE processo_id = ? ORDER BY id",
            (processo_id,),
        ).fetchall()
    return [
        PassoDetalhado(PassoTrace.model_validate_json(j), json.loads(p) if p else [])
        for j, p in linhas
    ]


@dataclass
class ResumoCusto:
    passos: int
    tokens_entrada: int
    tokens_saida: int
    ms: int
    custo_brl: float
    erros: int


def resumo_custo(processo_id: str) -> ResumoCusto:
    passos = listar_passos(processo_id)
    return ResumoCusto(
        passos=len(passos),
        tokens_entrada=sum(p.tokens_entrada for p in passos),
        tokens_saida=sum(p.tokens_saida for p in passos),
        ms=sum(p.ms for p in passos),
        custo_brl=round(sum(p.custo_brl for p in passos), 6),
        erros=sum(1 for p in passos if p.erro),
    )
