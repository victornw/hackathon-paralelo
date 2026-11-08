"""Custo e latência de um processo de homologação completo, com o LLM real.

Uso (carregue o .env antes, sem imprimir a chave):

    set -a; source .env; set +a
    .venv/bin/python -m evals.processo_completo --casos 1 2 3 --repeticoes 2

Dirige o app FastAPI em processo (TestClient) como um usuário: cria o processo,
envia a conta e a proposta, responde as perguntas do integrador (tabela
RESPOSTAS, chaveada por Pergunta.campo), aprova como engenheiro, deixa o
agente protocolar e avança o relógio e o portal simulados até onde a API deixa.
Nenhuma regra do produto é contornada: se a aprovação bloqueia, a execução
registra onde e por quê e segue para a próxima.

Os números vêm da tabela de trace (tokens, passos, erros). As chamadas ao
`ai_sdk.run` são medidas por um invólucro, porque o trace não separa o tempo
do modelo do tempo das ferramentas dentro de um passo do agente.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from app.core import arranjo, perguntas
from app.schemas import Etapa, Pergunta, Processo

RAIZ = Path(__file__).resolve().parents[1]
CONTAS = RAIZ / "fixtures" / "contas"
PASTA_PADRAO = Path("/tmp/gd-ev")
MAX_RODADAS = 5
MAX_TRANSICOES = 20
MAX_RETENTATIVAS = 3
ENGENHEIRO = "Eng. Eval (CREA sintético)"
PASSO_DECISAO = "modelo_agente_ai_sdk"
PREFIXOS_SEM_RESPOSTA = ("lembrete:", "falha:", "pendencia:")

# --- tabela de respostas ---------------------------------------------------------------


@dataclass(frozen=True)
class Contexto:
    gabarito: dict
    processo: Processo


Resposta = Callable[[Contexto], str]


def _fixa(texto: str) -> Resposta:
    return lambda _: texto


def _da_conta(chave: str) -> Resposta:
    return lambda c: str(c.gabarito["campos"][chave]["valor"])


def _bitola(c: Contexto) -> str:
    disjuntor = c.processo.visita.disjuntor_ca_a
    sugerida = None if disjuntor is None else arranjo.bitola_por_tabela(disjuntor)
    return f"{sugerida or 6:g}"


def _strings(c: Contexto) -> str:
    """Confirma as strings sugeridas; sem sugestão, reparte os módulos do gabarito entre os MPPT."""
    kit = c.processo.kit
    if kit is not None and kit.strings:
        return "sim"
    total = c.gabarito["kit"]["qtd_modulos"]
    mppt = max(1, min(kit.inversor.num_mppt if kit else 1, total))
    base, resto = divmod(total, mppt)
    return ", ".join(str(base + (i < resto)) for i in range(mppt))


RESPOSTAS: dict[str, Resposta] = {
    **{
        f"campos.{chave}": _da_conta(chave) for chave, _, _ in perguntas.CAMPOS_DA_CONTA
    },
    "relacao_cargas": _fixa(
        "Geladeira 250 W\nAr-condicionado 1400 W x2\nChuveiro elétrico 5500 W\n"
        "Iluminação e tomadas 800 W"
    ),
    "disjuntor_padrao_a": _fixa("40"),
    "bitola_ca_mm2": _bitola,
    "distancia_inversor_quadro_m": _fixa("8"),
    "coordenadas_padrao": _fixa("-3,7319, -38,5267"),
    "area_concessao": _fixa("Ceará"),
    "tipo_ramal": _fixa("aéreo"),
    "email_contato": _fixa("integrador.eval@exemplo.com"),
    "coef_temp_voc_pct_c": _fixa("-0,27"),
    "certificado_inmetro": _fixa("SIM-004314/2024"),
    "strings": _strings,
    "telefone": _fixa("(85) 90000-0000"),
    "qtd_ucs_credito": _fixa("1"),
    "modalidade_compensacao": _fixa("Autoconsumo local"),
    "dps_especificacao": _fixa("classe II, 275 V, 20 kA"),
}

# Perguntas do engenheiro que o script responde (o resto dele é aprovar).
CAMPOS_DO_ENGENHEIRO = frozenset({"strings", "dps_especificacao"})


def _falhas_abertas(p: Processo) -> list[str]:
    return [q.id for q in p.perguntas if q.id.startswith("falha:") and not q.resposta]


def a_responder(p: Processo) -> tuple[list[Pergunta], list[Pergunta]]:
    """(respondíveis, sem mapa): perguntas abertas do integrador, mais as do engenheiro
    em CAMPOS_DO_ENGENHEIRO. Lembretes, falhas e pendências não são perguntas de dados."""
    abertas = [
        q
        for q in p.perguntas
        if not q.resposta and not q.id.startswith(PREFIXOS_SEM_RESPOSTA)
    ]
    do_script = [
        q
        for q in abertas
        if q.destinatario == "integrador" or q.campo in CAMPOS_DO_ENGENHEIRO
    ]
    return (
        [q for q in do_script if q.campo in RESPOSTAS],
        [q for q in do_script if q.campo not in RESPOSTAS],
    )


def montar_respostas(p: Processo, gabarito: dict) -> list[dict[str, str]]:
    contexto = Contexto(gabarito, p)
    respondiveis, _ = a_responder(p)
    return [
        {"id": q.id, "resposta": RESPOSTAS[q.campo](contexto)} for q in respondiveis
    ]


# --- medição ---------------------------------------------------------------------------


@dataclass
class Medidor:
    chamadas_completar: int = 0
    ms_completar: int = 0
    ms_ferramentas: int = 0
    ms_decisao: int = 0
    erros_sdk: list[str] = field(default_factory=list)


@contextmanager
def medir() -> Iterator[Medidor]:
    """Mede as chamadas `complete` ao modelo e o tempo das ferramentas do orquestrador."""
    from app.core import ai_sdk, orquestrador

    m = Medidor()
    run, rodar = ai_sdk.run, orquestrador._rodar

    def _nada() -> None:
        return None

    def _ms(desde: float) -> int:
        return int((time.perf_counter() - desde) * 1000)

    def decisao_medida(handler: Callable) -> tuple[Callable, Callable[[], None]]:
        """Tempo do modelo no agente: do fim de `state` até o `execute` que ele pediu
        (ou até o fim da execução, se ele não pediu nenhum). O `ms` do trace do passo
        do agente soma mais que o relógio da parede em alguns passos; não é usado."""
        esperando: list[float] = []

        def fechar() -> None:
            if esperando:
                m.ms_decisao += _ms(esperando.pop())

        def medido(method: str, params: dict) -> dict:
            if method == "execute":
                fechar()
            resposta = handler(method, params)
            if method == "state":
                esperando[:] = [time.perf_counter()]
            return resposta

        return medido, fechar

    def run_medido(request: dict, handler: Callable | None = None) -> dict:
        inicio = time.perf_counter()
        fechar = _nada
        if request.get("mode") == "agent" and handler is not None:
            handler, fechar = decisao_medida(handler)
        try:
            return run(request, handler)
        except ai_sdk.SDKError as exc:
            m.erros_sdk.append(f"{request.get('mode')}: {exc}")
            raise
        finally:
            fechar()
            if request.get("mode") == "complete":
                m.chamadas_completar += 1
                m.ms_completar += _ms(inicio)

    def rodar_medido(*args, **kwargs) -> None:
        inicio = time.perf_counter()
        try:
            rodar(*args, **kwargs)
        finally:
            m.ms_ferramentas += int((time.perf_counter() - inicio) * 1000)

    ai_sdk.run, orquestrador._rodar = run_medido, rodar_medido
    try:
        yield m
    finally:
        ai_sdk.run, orquestrador._rodar = run, rodar


# --- execução --------------------------------------------------------------------------


@dataclass
class Execucao:
    caso: int
    repeticao: int
    processo_id: str = ""
    etapa_final: str = ""
    aprovado: bool = False
    bloqueio: str = ""
    parou_em: str = ""
    rodadas: int = 0
    retentativas: int = 0
    chamadas_llm: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    ms_llm: int = 0
    ms_agente: int = 0
    ms_decisao: int = 0
    ms_ferramentas: int = 0
    ms_completar: int = 0
    segundos: float = 0.0
    erros: list[str] = field(default_factory=list)
    trilha: list[str] = field(default_factory=list)


class Falha(Exception):
    """Ponto em que o fluxo não anda sem contornar uma regra do produto."""


class Usuario:
    """O integrador e o engenheiro agindo pela API."""

    def __init__(self, cliente, caso: int, execucao: Execucao):
        self.http = cliente
        self.caso = caso
        self.ex = execucao
        self.gabarito = json.loads(
            (CONTAS / f"cliente_{caso}_gabarito.json").read_text()
        )

    def _chamar(
        self, metodo: str, url: str, esperado: tuple[int, ...] = (200, 201, 202), **kw
    ):
        resposta = self.http.request(metodo, url, **kw)
        self.ex.trilha.append(
            f"{metodo} {url.removeprefix('/api')} -> {resposta.status_code}"
        )
        if resposta.status_code not in esperado:
            raise Falha(f"{metodo} {url}: {resposta.status_code} {resposta.text[:300]}")
        return resposta

    def processo(self) -> Processo:
        return Processo.model_validate(
            self._chamar("GET", f"/api/processos/{self.ex.processo_id}").json()
        )

    def criar(self) -> None:
        self.ex.processo_id = self._chamar("POST", "/api/processos", json={}).json()[
            "id"
        ]

    def enviar(self, tipo: str, nome: str) -> None:
        arquivo = CONTAS / nome
        self._chamar(
            "POST",
            f"/api/processos/{self.ex.processo_id}/arquivos",
            data={"tipo": tipo},
            files={"file": (nome, arquivo.read_bytes(), "application/pdf")},
        )

    def montar_pacote(self) -> None:
        """Responde (a API já roda o orquestrador) e repete até o pacote ir para a revisão."""
        for rodada in range(1, MAX_RODADAS + 1):
            p = self.processo()
            if p.etapa != Etapa.MONTAGEM:
                return
            respondiveis, sem_mapa = a_responder(p)
            if sem_mapa:
                raise Falha(
                    "pergunta sem resposta mapeada: "
                    + "; ".join(f"{q.campo} ({q.texto[:80]})" for q in sem_mapa)
                )
            self.ex.rodadas = rodada
            if respondiveis:
                self._chamar(
                    "POST",
                    f"/api/processos/{p.id}/respostas",
                    json=montar_respostas(p, self.gabarito),
                )
                continue
            if not _falhas_abertas(p):
                raise Falha(
                    "montagem parada sem pergunta aberta nem falha para refazer"
                )
            self._chamar(
                "POST", f"/api/processos/{p.id}/rodar", params={"refazer": True}
            )
        if self.processo().etapa == Etapa.MONTAGEM:
            raise Falha(f"pacote não chegou à revisão em {MAX_RODADAS} rodadas")

    def aprovar(self) -> None:
        """Revisão do engenheiro. Se a R05 pede confirmação dele, ele confirma e tenta de novo."""
        p = self.processo()
        if p.etapa != Etapa.EM_REVISAO:
            raise Falha(f"pacote não chegou à revisão (etapa {p.etapa.value})")
        url = f"/api/processos/{p.id}/revisao"
        resposta = self._chamar(
            "POST", url, esperado=(200, 409), json={"engenheiro": ENGENHEIRO}
        )
        if resposta.status_code == 409 and self._r05_confirmavel():
            self._chamar(
                "POST",
                f"/processos/{p.id}/regras/R05/confirmar",
                esperado=(200, 303, 409),
                data={"engenheiro": ENGENHEIRO},
            )
            resposta = self._chamar(
                "POST", url, esperado=(200, 409), json={"engenheiro": ENGENHEIRO}
            )
        if resposta.status_code == 409:
            self.ex.bloqueio = resposta.json()["detail"]
            raise Falha("aprovação bloqueada")
        self.ex.aprovado = True

    def _r05_confirmavel(self) -> bool:
        return any(
            r.regra_id == "R05" and r.valores.get("confirmavel") == "sim"
            for r in self.processo().regras
        )

    def rodar(self, refazer: bool = False) -> None:
        self._chamar(
            "POST",
            f"/api/processos/{self.ex.processo_id}/rodar",
            params={"refazer": refazer},
        )

    def avancar_relogio(self) -> None:
        self._chamar("POST", "/api/relogio/avancar", json={"dias": 1})

    def portal(self, acao: str) -> None:
        self._chamar("POST", f"/api/processos/{self.ex.processo_id}/portal/{acao}")

    def reaprovar_pendencia(self) -> None:
        """Depois de classificar a pendência o agente zera a aprovação: o engenheiro aprova de novo."""
        resposta = self._chamar(
            "POST",
            f"/api/processos/{self.ex.processo_id}/revisao",
            esperado=(200, 409),
            json={"engenheiro": ENGENHEIRO},
        )
        if resposta.status_code == 409:
            self.ex.bloqueio = resposta.json()["detail"]
            raise Falha("reaprovação da pendência bloqueada")


# O que fazer em cada etapa do portal para o processo andar.
ACOES: dict[Etapa, Callable[[Usuario], None]] = {
    Etapa.EM_REVISAO: Usuario.rodar,
    Etapa.PROTOCOLADO: Usuario.avancar_relogio,
    Etapa.PENDENCIA: Usuario.reaprovar_pendencia,
    Etapa.ORCAMENTO_EMITIDO: lambda u: u.portal("aprovar-orcamento"),
    Etapa.ORCAMENTO_APROVADO: lambda u: u.portal("solicitar-vistoria"),
    Etapa.VISTORIA_SOLICITADA: Usuario.avancar_relogio,
    Etapa.VISTORIA: Usuario.avancar_relogio,
    Etapa.MEDIDOR: Usuario.avancar_relogio,
}


def percorrer_portal(u: Usuario) -> None:
    retentativas = 0
    for _ in range(MAX_TRANSICOES):
        p = u.processo()
        u.ex.etapa_final = p.etapa.value
        if p.etapa == Etapa.CONCLUIDO:
            return
        if _falhas_abertas(p):
            retentativas += 1
            if retentativas > MAX_RETENTATIVAS:
                raise Falha(
                    f"agente falhou {MAX_RETENTATIVAS} vezes seguidas em '{p.etapa.value}'"
                )
            u.ex.retentativas += 1
            u.rodar(refazer=True)
            continue
        retentativas = 0
        if p.etapa not in ACOES:
            raise Falha(f"etapa {p.etapa.value} sem ação possível pela API")
        ACOES[p.etapa](u)
        depois = u.processo()
        if depois.etapa == p.etapa and len(depois.eventos) == len(p.eventos):
            raise Falha(f"a ação em '{p.etapa.value}' não mudou o processo")
    raise Falha(f"mais de {MAX_TRANSICOES} transições sem concluir")


def _consolidar_trace(ex: Execucao, m: Medidor) -> None:
    from app.tracing import listar_passos, resumo_custo

    resumo = resumo_custo(ex.processo_id)
    passos = listar_passos(ex.processo_id)
    decisoes = [s for s in passos if s.passo == PASSO_DECISAO]
    ex.tokens_entrada, ex.tokens_saida = resumo.tokens_entrada, resumo.tokens_saida
    ex.ms_agente = sum(s.ms for s in decisoes)
    ex.ms_completar, ex.ms_ferramentas = m.ms_completar, m.ms_ferramentas
    ex.chamadas_llm = len(decisoes) + m.chamadas_completar
    ex.ms_decisao = m.ms_decisao
    ex.ms_llm = m.ms_completar + m.ms_decisao
    ex.erros = [f"{s.passo}: {s.erro[:160]}" for s in passos if s.erro]
    ex.erros += [f"SDK {e}" for e in m.erros_sdk]


def executar_caso(cliente, caso: int, repeticao: int) -> Execucao:
    ex = Execucao(caso, repeticao)
    u = Usuario(cliente, caso, ex)
    inicio = time.perf_counter()
    with medir() as m:
        try:
            u.criar()
            u.enviar("conta", f"cliente_{caso}_conta.pdf")
            u.enviar("proposta", f"cliente_{caso}_proposta.pdf")
            u.montar_pacote()
            u.aprovar()
            percorrer_portal(u)
        except Falha as exc:
            ex.parou_em = str(exc)
        except Exception as exc:  # noqa: BLE001 - uma execução quebrada não derruba as outras
            ex.parou_em = f"{type(exc).__name__}: {exc}"
    ex.segundos = time.perf_counter() - inicio
    if ex.processo_id:
        final = u.processo()
        ex.etapa_final = final.etapa.value
        abertas = [
            q.id
            for q in final.perguntas
            if q.id.startswith("falha:") and not q.resposta
        ]
        _consolidar_trace(ex, m)
        ex.erros += [f"pergunta aberta {i}" for i in abertas]
    return ex


# --- relatório -------------------------------------------------------------------------

COLUNAS = (
    "caso",
    "rep",
    "etapa final",
    "aprovado",
    "rodadas",
    "retentativas",
    "chamadas LLM",
    "tokens in",
    "tokens out",
    "LLM s",
    "total s",
    "erros",
)


def _linha(e: Execucao) -> tuple:
    return (
        e.caso,
        e.repeticao,
        e.etapa_final,
        "sim" if e.aprovado else "não",
        e.rodadas,
        e.retentativas,
        e.chamadas_llm,
        e.tokens_entrada,
        e.tokens_saida,
        f"{e.ms_llm / 1000:.1f}",
        f"{e.segundos:.1f}",
        len(e.erros),
    )


def _tabela(cabecalho: tuple[str, ...], linhas: list[tuple]) -> str:
    corpo = [f"| {' | '.join(map(str, l))} |" for l in linhas]
    return "\n".join(
        [f"| {' | '.join(cabecalho)} |", f"|{'---|' * len(cabecalho)}", *corpo]
    )


def relatorio(execucoes: list[Execucao]) -> str:
    n = len(execucoes)
    media = lambda f: sum(f(e) for e in execucoes) / n
    concluidas = sum(e.etapa_final == Etapa.CONCLUIDO.value for e in execucoes)
    medias = (
        f"\nMédias de {n} execução(ões), {concluidas} concluída(s): "
        f"{media(lambda e: e.chamadas_llm):.1f} chamadas LLM, "
        f"{media(lambda e: e.tokens_entrada):.0f} tokens in, "
        f"{media(lambda e: e.tokens_saida):.0f} tokens out, "
        f"{media(lambda e: e.ms_llm) / 1000:.1f} s de LLM, "
        f"{media(lambda e: e.segundos):.1f} s de relógio.\n"
        f"Tokens gastos no total: {sum(e.tokens_entrada + e.tokens_saida for e in execucoes)} "
        f"({sum(e.tokens_entrada for e in execucoes)} in, "
        f"{sum(e.tokens_saida for e in execucoes)} out).\n"
    )
    detalhes = []
    for e in execucoes:
        detalhes.append(
            f"- caso {e.caso} rep {e.repeticao} ({e.processo_id}): "
            f"parou em: {e.parou_em or 'não parou'}; bloqueio: {e.bloqueio or 'nenhum'}; "
            f"ms decisão (medido) {e.ms_decisao}, ferramentas {e.ms_ferramentas}, "
            f"passos do agente no trace {e.ms_agente}, "
            f"completar {e.ms_completar}; erros: {e.erros or 'nenhum'}"
        )
    return "\n".join(
        [_tabela(COLUNAS, [_linha(e) for e in execucoes]), medias, *detalhes]
    )


# --- entrada ---------------------------------------------------------------------------


def preparar_ambiente(pasta: Path, limpar: bool) -> None:
    if limpar:
        (pasta / "processos.db").unlink(missing_ok=True)
        for sub in ("docs", "uploads"):
            shutil.rmtree(pasta / sub, ignore_errors=True)
    pasta.mkdir(parents=True, exist_ok=True)
    os.environ["DB_PATH"] = str(pasta / "processos.db")
    os.environ["DOCS_DIR"] = str(pasta / "docs")
    os.environ["UPLOADS_DIR"] = str(pasta / "uploads")


def main(argv: list[str] | None = None) -> list[Execucao]:
    ap = argparse.ArgumentParser(description="Custo e latência por processo completo.")
    ap.add_argument("--casos", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--repeticoes", type=int, default=1)
    ap.add_argument("--pasta", type=Path, default=PASTA_PADRAO)
    ap.add_argument(
        "--agente",
        choices=("sdk", "deterministico"),
        default="sdk",
        help="sdk: o modelo escolhe cada passo (padrão do produto); deterministico: "
        "ordem canônica sem modelo de decisão (extração e pendências seguem com LLM)",
    )
    ap.add_argument("--manter", action="store_true", help="não apaga o banco anterior")
    args = ap.parse_args(argv)
    preparar_ambiente(args.pasta, limpar=not args.manter)

    from fastapi.testclient import TestClient

    from app.core import llm
    from app.main import app

    if args.agente == "deterministico":
        disponivel = llm.disponivel
        llm.disponivel = lambda papel: papel != "decisao" and disponivel(papel)
    if not llm.disponivel("extracao"):
        raise SystemExit(
            "LLM não configurado: carregue o .env (FEATHERLESS_API_KEY, MODELO_PRINCIPAL)."
        )
    cliente = TestClient(app)  # sem `with`: não recria os casos de demonstração
    execucoes = []
    for repeticao in range(1, args.repeticoes + 1):
        for caso in args.casos:
            ex = executar_caso(cliente, caso, repeticao)
            execucoes.append(ex)
            print(
                f"caso {caso} rep {repeticao}: {ex.etapa_final} ({ex.segundos:.0f} s)",
                flush=True,
            )
    print()
    print(relatorio(execucoes))
    return execucoes


if __name__ == "__main__":
    main()
