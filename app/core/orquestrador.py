"""Orquestrador: guardas determinísticas e escolha limitada do LLM.

Cada passo tem uma guarda pura (`_ENTRADAS`) que devolve o hash das entradas do
passo, ou None quando a pré-condição não vale. Um passo só está disponível se
o hash difere do que a memória registrou como já tratado; por isso rodar de
novo sem entrada nova não faz nada. Os passos de montagem andam em estágios:
um estágio só abre quando o anterior não tem nada pendente.

O LLM nunca decide se uma regra passa nem se um passo pode rodar: só escolhe,
entre os passos que as guardas liberaram, qual vem primeiro, usando ToolLoopAgent
do Vercel AI SDK. Sem modelo configurado, vale a ordem canônica determinística. Um passo calcula sobre um retrato do
processo e devolve uma função `aplicar`; ela só entra se as entradas do passo
não mudaram durante o cálculo (senão o resultado é descartado e o passo roda de
novo), então a API pode gravar respostas a qualquer momento sem perder dados.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from functools import lru_cache
from itertools import chain
from pathlib import Path

from pydantic import BaseModel

from app.core import ai_sdk, arranjo, extracao, llm, perguntas
from app.core import regras as conferidor
from app.core import repositorio as repo
from app.core.aprovacao import REGRAS_OBRIGATORIAS, bloqueios_aprovacao
from app.docs import gerar as gerador
from app.portal_sim import pendencias, portal, prazos
from app.portal_sim.relogio import hoje
from app.schemas import (
    CampoExtraido,
    DadosVisita,
    Etapa,
    EventoPortal,
    PassoTrace,
    Pergunta,
    Processo,
    StatusRegra,
)
from app.tracing import processo_atual, registrar_uso, trace
from app.tracing.trace import custo_por_tokens, gravar_passo

MAX_PASSOS = 30
TENTATIVAS = 3
FONTE_RESPOSTA = "resposta_integrador"
PREFIXOS_PROPRIOS = ("falha:", "kit:", "pendencia:", "lembrete:")


class Passo(StrEnum):
    extrair_conta = "extrair_conta"
    extrair_kit = "extrair_kit"
    extrair_padrao = "extrair_padrao"
    verificar_arranjo = "verificar_arranjo"
    perguntar = "perguntar"
    gerar_documentos = "gerar_documentos"
    conferir = "conferir"
    enviar_revisao = "enviar_revisao"
    protocolar = "protocolar"
    consultar_portal = "consultar_portal"
    tratar_pendencia = "tratar_pendencia"
    reenviar = "reenviar"


_ESTAGIOS: tuple[tuple[Passo, ...], ...] = (
    (Passo.extrair_conta, Passo.extrair_kit, Passo.extrair_padrao),
    (Passo.verificar_arranjo,),
    (Passo.perguntar,),
    (Passo.gerar_documentos,),
    (Passo.conferir,),
    (Passo.enviar_revisao,),
    (Passo.protocolar, Passo.consultar_portal, Passo.tratar_pendencia, Passo.reenviar),
)
assert set(chain.from_iterable(_ESTAGIOS)) == set(Passo)

_TIPOS_DO_PASSO: dict[Passo, tuple[str, ...]] = {
    Passo.extrair_conta: ("conta",),
    Passo.extrair_kit: ("proposta", "datasheet"),
    Passo.extrair_padrao: ("padrao",),
}

_DESCRICAO: dict[Passo, str] = {
    Passo.extrair_conta: "ler a conta de luz",
    Passo.extrair_kit: "ler a proposta e os datasheets do kit",
    Passo.extrair_padrao: "ler a foto do padrão de entrada",
    Passo.verificar_arranjo: "conferir o arranjo do kit e escolher disjuntor por tabela",
    Passo.perguntar: "registrar as perguntas que faltam para fechar o pacote",
    Passo.gerar_documentos: "gerar solicitação, memorial e unifilar",
    Passo.conferir: "aplicar as regras R01 a R05",
    Passo.enviar_revisao: "enviar o pacote conferido para a revisão do engenheiro",
    Passo.protocolar: "protocolar no portal depois da aprovação do engenheiro",
    Passo.consultar_portal: "consultar o status no portal",
    Passo.tratar_pendencia: "classificar a pendência apontada pela distribuidora",
    Passo.reenviar: "reenviar a documentação corrigida ao portal",
}

Aplicar = Callable[[Processo], None]
Arquivos = dict[str, list[Path]]


@dataclass(frozen=True)
class Estado:
    processo: Processo
    arquivos: Arquivos
    memoria: dict[str, str]
    dia: date


# --- hashes e guardas ----------------------------------------------------------------


def _hash(*partes: object) -> str:
    bruto = json.dumps(partes, default=str, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(bruto.encode()).hexdigest()[:16]


def _dump(modelo: BaseModel | None) -> object:
    return None if modelo is None else modelo.model_dump(mode="json")


@lru_cache(maxsize=512)
def _sha_arquivo(caminho: str, mtime_ns: int, tamanho: int) -> str:
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


def _sha(arquivo: Path) -> str:
    st = arquivo.stat()
    return _sha_arquivo(str(arquivo), st.st_mtime_ns, st.st_size)


def _sem_trace(ferramenta: Callable) -> Callable:
    """A guarda avalia a ferramenta a cada volta; só a execução grava trace."""
    return getattr(ferramenta, "__wrapped__", ferramenta)


def _em_montagem(e: Estado) -> bool:
    return e.processo.etapa == Etapa.MONTAGEM


def _entrada_arquivos(passo: Passo) -> Callable[[Estado], str | None]:
    def entrada(e: Estado) -> str | None:
        if not _em_montagem(e):
            return None
        lidos = [
            (a.name, _sha(a))
            for t in _TIPOS_DO_PASSO[passo]
            for a in e.arquivos.get(t, [])
        ]
        return _hash(lidos) if lidos else None

    return entrada


def _entrada_verificar(e: Estado) -> str | None:
    p = e.processo
    if not _em_montagem(e) or p.kit is None:
        return None
    return _hash(_dump(p.kit), _dump(p.visita))


def _delta_perguntas(
    p: Processo, pendentes: list[Pergunta]
) -> tuple[list[Pergunta], list[str]]:
    existentes = {q.id for q in p.perguntas}
    ids = {q.id for q in pendentes}
    novas = [q for q in pendentes if q.id not in existentes]
    obsoletas = [
        q.id
        for q in p.perguntas
        if not q.resposta and not q.id.startswith(PREFIXOS_PROPRIOS) and q.id not in ids
    ]
    return novas, obsoletas


def _entrada_perguntar(e: Estado) -> str | None:
    if not _em_montagem(e):
        return None
    novas, obsoletas = _delta_perguntas(
        e.processo, _sem_trace(perguntas.perguntas_pendentes)(e.processo)
    )
    return _hash([q.id for q in novas], obsoletas) if novas or obsoletas else None


def _entradas_documentos(p: Processo) -> str:
    # Respostas do engenheiro também vão para os documentos (ex.: DPS no memorial).
    respostas = sorted(
        (q.id, q.resposta)
        for q in p.perguntas
        if q.resposta and not q.id.startswith("falha:")
    )
    return _hash(
        {k: _dump(v) for k, v in p.campos.items()},
        _dump(p.kit),
        _dump(p.visita),
        respostas,
    )


def _entrada_gerar(e: Estado) -> str | None:
    if not _em_montagem(e) or e.processo.kit is None:
        return None
    return _entradas_documentos(e.processo)


def _entrada_conferir(e: Estado) -> str | None:
    p = e.processo
    if not _em_montagem(e) or not p.documentos:
        return None
    docs = [(d.nome_arquivo, d.gerado_em.isoformat()) for d in p.documentos]
    return _hash(_entradas_documentos(p), docs)


def _perguntas_abertas_do_integrador(p: Processo) -> list[Pergunta]:
    return [q for q in p.perguntas if q.destinatario == "integrador" and not q.resposta]


def _falhas_abertas(p: Processo) -> list[Pergunta]:
    return [q for q in p.perguntas if q.id.startswith("falha:") and not q.resposta]


def _entrada_enviar_revisao(e: Estado) -> str | None:
    p = e.processo
    conferido = _entrada_conferir(e)
    if conferido is None or e.memoria.get(Passo.conferir) != conferido:
        return None
    if not REGRAS_OBRIGATORIAS <= {r.regra_id for r in p.regras}:
        return None
    if any(r.status == StatusRegra.REPROVADA for r in p.regras):
        return None
    if _perguntas_abertas_do_integrador(p) or _falhas_abertas(p):
        return None
    return _hash(conferido, [(r.regra_id, r.status.value) for r in p.regras])


def _entrada_protocolar(e: Estado) -> str | None:
    p = e.processo
    if p.etapa != Etapa.EM_REVISAO or not p.revisado_por or p.numero_solicitacao:
        return None
    if bloqueios_aprovacao(p):
        return None
    return _hash(p.revisado_por, p.revisado_em)


def _entrada_consultar(e: Estado) -> str | None:
    p = e.processo
    if not p.numero_solicitacao or p.etapa == Etapa.CONCLUIDO:
        return None
    return _hash(e.dia.isoformat(), len(p.eventos))


def _pendencia_aberta(p: Processo) -> EventoPortal | None:
    ultimo = p.eventos[-1] if p.eventos else None
    return ultimo if ultimo and ultimo.etapa == Etapa.PENDENCIA else None


def _entrada_tratar(e: Estado) -> str | None:
    p = e.processo
    ev = _pendencia_aberta(p)
    if ev is None or not ev.motivo_pendencia or ev.categoria_pendencia:
        return None
    return _hash(p.numero_solicitacao, ev.data, ev.motivo_pendencia)


def _entrada_reenviar(e: Estado) -> str | None:
    p = e.processo
    ev = _pendencia_aberta(p)
    if p.etapa != Etapa.PENDENCIA or not p.revisado_por or not p.numero_solicitacao:
        return None
    if ev is None or not ev.categoria_pendencia:
        return None
    if bloqueios_aprovacao(p):
        return None
    return _hash(ev.data, ev.motivo_pendencia, p.revisado_em)


_ENTRADAS: dict[Passo, Callable[[Estado], str | None]] = {
    Passo.extrair_conta: _entrada_arquivos(Passo.extrair_conta),
    Passo.extrair_kit: _entrada_arquivos(Passo.extrair_kit),
    Passo.extrair_padrao: _entrada_arquivos(Passo.extrair_padrao),
    Passo.verificar_arranjo: _entrada_verificar,
    Passo.perguntar: _entrada_perguntar,
    Passo.gerar_documentos: _entrada_gerar,
    Passo.conferir: _entrada_conferir,
    Passo.enviar_revisao: _entrada_enviar_revisao,
    Passo.protocolar: _entrada_protocolar,
    Passo.consultar_portal: _entrada_consultar,
    Passo.tratar_pendencia: _entrada_tratar,
    Passo.reenviar: _entrada_reenviar,
}


def passos_disponiveis(
    processo: Processo,
    arquivos: Arquivos,
    memoria: dict[str, str],
    dia: date | None = None,
) -> list[Passo]:
    """Passos que podem rodar agora, na ordem canônica. Puro: o dia do relógio
    simulado entra como argumento (padrão: hoje())."""
    estado = Estado(processo, arquivos, memoria, dia or hoje())
    for estagio in _ESTAGIOS:
        pendentes = [
            p
            for p in estagio
            if (h := _ENTRADAS[p](estado)) is not None and h != memoria.get(p)
        ]
        if pendentes:
            return pendentes
    return []


# --- aplicação de resultados ----------------------------------------------------------


def _confirmado(campo: object) -> bool:
    return (
        isinstance(campo, CampoExtraido)
        and campo.fonte is not None
        and campo.fonte.documento == FONTE_RESPOSTA
    )


def _trocar_perguntas(p: Processo, prefixo: str, novas: list[Pergunta]) -> None:
    """Troca as perguntas abertas com o prefixo pelas `novas`; as respondidas ficam."""
    mantidas = [
        q for q in p.perguntas if not (q.id.startswith(prefixo) and not q.resposta)
    ]
    ids = {q.id for q in mantidas}
    p.perguntas = [*mantidas, *(q for q in novas if q.id not in ids)]


def _mesclar_regras(atuais: list, novas: list) -> list:
    ids = {r.regra_id for r in novas}
    return sorted(
        [*(r for r in atuais if r.regra_id not in ids), *novas],
        key=lambda r: r.regra_id,
    )


_LEMBRETES: dict[Etapa, tuple[str, str]] = {
    Etapa.ORCAMENTO_EMITIDO: (
        "aprovar_orcamento",
        "Orçamento emitido. Aprove no Portal GD até {vencimento} ({fonte}); depois do prazo ele perde a validade.",
    ),
    Etapa.ORCAMENTO_APROVADO: (
        "devolver_contratos",
        "Orçamento aprovado. Devolva os contratos assinados até {vencimento} ({fonte}) e, com a instalação pronta, solicite a vistoria no Portal GD.",
    ),
}


def _atualizar_lembretes(p: Processo) -> None:
    """O agente só lembra o integrador: aprovar o orçamento e pedir a vistoria
    são ações dele no portal. O lembrete da etapa que passou é encerrado."""
    atual = f"lembrete:{p.etapa.value}"
    for q in p.perguntas:
        if q.id.startswith("lembrete:") and q.id != atual and not q.resposta:
            q.resposta = "Etapa concluída no portal."
            q.respondida_em = repo.agora()
    if p.etapa not in _LEMBRETES or any(q.id == atual for q in p.perguntas):
        return
    tipo, modelo = _LEMBRETES[p.etapa]
    prazo = next((x for x in p.prazos if x.tipo == tipo), None)
    texto = modelo.format(
        vencimento=prazo.vencimento.strftime("%d/%m/%Y")
        if prazo
        else "o prazo da norma",
        fonte=prazo.fonte if prazo else "norma Enel",
    )
    p.perguntas.append(
        Pergunta(id=atual, campo=tipo, texto=texto, destinatario="integrador")
    )


def _aplicar_eventos(p: Processo, eventos: list[EventoPortal]) -> None:
    """Sincroniza o processo com o portal. O portal não guarda a classificação
    da pendência, então ela é preservada dos eventos que já tínhamos."""
    classificados = {
        (e.etapa, e.data, e.motivo_pendencia): e
        for e in p.eventos
        if e.categoria_pendencia
    }
    novos = []
    for ev in eventos:
        antigo = classificados.get((ev.etapa, ev.data, ev.motivo_pendencia))
        if antigo and not ev.categoria_pendencia:
            ev = ev.model_copy(
                update={
                    "categoria_pendencia": antigo.categoria_pendencia,
                    "correcao_proposta": antigo.correcao_proposta,
                }
            )
        novos.append(ev)
    p.eventos = novos
    if novos:
        p.etapa = novos[-1].etapa
    p.prazos = prazos.calcular_prazos(p)
    _atualizar_lembretes(p)


# --- execução dos passos --------------------------------------------------------------

_EXECUTORES: dict[Passo, Callable[[Processo, Arquivos], Aplicar]] = {}


def _executor(passo: Passo):
    def registrar(func):
        _EXECUTORES[passo] = func
        return func

    return registrar


@_executor(Passo.extrair_conta)
def _executar_extrair_conta(p: Processo, arquivos: Arquivos) -> Aplicar:
    novos: dict[str, CampoExtraido] = {}
    for arquivo in arquivos["conta"]:
        for chave, campo in extracao.extrair_conta(arquivo).items():
            if chave not in novos or campo.confianca > novos[chave].confianca:
                novos[chave] = campo

    def aplicar(q: Processo) -> None:
        for chave, campo in novos.items():
            if not _confirmado(q.campos.get(chave)):
                q.campos[chave] = campo

    return aplicar


@_executor(Passo.extrair_kit)
def _executar_extrair_kit(p: Processo, arquivos: Arquivos) -> Aplicar:
    enviados = [*arquivos["proposta"], *arquivos["datasheet"]]
    try:
        kit = extracao.extrair_kit(enviados)
    except extracao.KitIncompleto as exc:
        faltas = [
            Pergunta(
                id=f"kit:{campo}",
                campo=f"kit.{campo}",
                texto=(
                    f"Não consegui ler '{campo}' na proposta e nos datasheets enviados. "
                    "Envie o datasheet ou a proposta com esse dado."
                ),
            )
            for campo in exc.faltando
        ]
        return lambda q: _trocar_perguntas(q, "kit:", faltas)

    def aplicar(q: Processo) -> None:
        q.kit = kit
        _trocar_perguntas(q, "kit:", [])

    return aplicar


@_executor(Passo.extrair_padrao)
def _executar_extrair_padrao(p: Processo, arquivos: Arquivos) -> Aplicar:
    lidos: dict[str, object] = {}
    for foto in arquivos["padrao"]:
        visita = extracao.extrair_padrao(foto)
        lidos.update(
            {
                n: v
                for n in DadosVisita.model_fields
                if (v := getattr(visita, n)) not in (None, [])
            }
        )

    def aplicar(q: Processo) -> None:
        for nome, valor in lidos.items():
            if not _confirmado(getattr(q.visita, nome)):
                setattr(q.visita, nome, valor)

    return aplicar


@_executor(Passo.verificar_arranjo)
def _executar_verificar_arranjo(p: Processo, arquivos: Arquivos) -> Aplicar:
    kit, visita, resultados = arranjo.verificar_arranjo(p.kit, p.visita)

    def aplicar(q: Processo) -> None:
        q.kit = kit
        q.visita = visita
        q.regras = _mesclar_regras(q.regras, resultados)

    return aplicar


@_executor(Passo.perguntar)
def _executar_perguntar(p: Processo, arquivos: Arquivos) -> Aplicar:
    novas, obsoletas = _delta_perguntas(p, perguntas.perguntas_pendentes(p))

    def aplicar(q: Processo) -> None:
        q.perguntas = [x for x in q.perguntas if x.id not in obsoletas or x.resposta]
        q.perguntas.extend(novas)

    return aplicar


@_executor(Passo.gerar_documentos)
def _executar_gerar_documentos(p: Processo, arquivos: Arquivos) -> Aplicar:
    documentos = gerador.gerar_documentos(p)

    def aplicar(q: Processo) -> None:
        q.documentos = documentos

    return aplicar


@_executor(Passo.conferir)
def _executar_conferir(p: Processo, arquivos: Arquivos) -> Aplicar:
    resultados = conferidor.conferir(p)

    def aplicar(q: Processo) -> None:
        q.regras = resultados

    return aplicar


@_executor(Passo.enviar_revisao)
@trace("enviar_revisao")
def _executar_enviar_revisao(p: Processo, arquivos: Arquivos) -> Aplicar:
    contagem = {s: sum(1 for r in p.regras if r.status == s) for s in StatusRegra}
    registrar_uso(
        decisao=(
            f"Pacote conferido ({contagem[StatusRegra.APROVADA]} aprovadas, "
            f"{contagem[StatusRegra.INCERTA]} incertas) e enviado à revisão do engenheiro."
        )
    )

    def aplicar(q: Processo) -> None:
        q.etapa = Etapa.EM_REVISAO

    return aplicar


@_executor(Passo.protocolar)
def _executar_protocolar(p: Processo, arquivos: Arquivos) -> Aplicar:
    numero = portal.protocolar(p)

    def aplicar(q: Processo) -> None:
        q.numero_solicitacao = numero
        q.etapa = Etapa.PROTOCOLADO

    return aplicar


def _valor_conta(p: Processo, chave: str) -> str:
    campo = p.campos.get(chave)
    if campo is None or campo.valor is None:
        raise ValueError(
            f"Não há '{chave}' lido da conta de luz para consultar o portal."
        )
    return str(campo.valor)


@_executor(Passo.consultar_portal)
@trace("consultar_portal")
def _executar_consultar_portal(p: Processo, arquivos: Arquivos) -> Aplicar:
    if not p.email_contato:
        raise ValueError("Sem e-mail de contato para consultar o portal.")
    eventos = portal.consultar_status(
        _valor_conta(p, "uc"), p.email_contato, p.numero_solicitacao
    )
    ultima = eventos[-1].etapa.value if eventos else "sem eventos"
    registrar_uso(
        decisao=f"Portal consultado: {len(eventos)} evento(s), etapa {ultima}."
    )
    return lambda q: _aplicar_eventos(q, eventos)


def _id_pendencia(ev: EventoPortal) -> str:
    return f"pendencia:{ev.data.isoformat()}"


@_executor(Passo.tratar_pendencia)
@trace("tratar_pendencia")
def _executar_tratar_pendencia(p: Processo, arquivos: Arquivos) -> Aplicar:
    ev = _pendencia_aberta(p)
    categoria, correcao = pendencias.classificar_pendencia(ev.motivo_pendencia)
    descricao = pendencias.CATEGORIAS.get(categoria, {}).get("descricao", categoria)
    prazo = next(
        (x for x in prazos.calcular_prazos(p) if x.tipo == "sanar_pendencia"), None
    )
    limite = (
        f" Prazo para sanar: {prazo.vencimento.strftime('%d/%m/%Y')} ({prazo.fonte})."
        if prazo
        else ""
    )
    pergunta = Pergunta(
        id=_id_pendencia(ev),
        campo="pendencia",
        destinatario="engenheiro",
        texto=(
            f"A distribuidora apontou uma pendência na solicitação {p.numero_solicitacao}: "
            f'"{ev.motivo_pendencia}" Categoria: {descricao}. Correção proposta: {correcao}{limite} '
            "Responda com a correção a enviar, se for outra, e aprove a revisão para reenviar."
        ),
    )
    registrar_uso(
        decisao=f"Pendência classificada como {categoria}; aguardando nova aprovação do engenheiro."
    )

    def aplicar(q: Processo) -> None:
        q.eventos = [
            e.model_copy(
                update={"categoria_pendencia": categoria, "correcao_proposta": correcao}
            )
            if (e.etapa, e.data, e.motivo_pendencia)
            == (ev.etapa, ev.data, ev.motivo_pendencia)
            else e
            for e in q.eventos
        ]
        q.revisado_por = None
        q.revisado_em = None
        q.etapa = Etapa.PENDENCIA
        if all(x.id != pergunta.id for x in q.perguntas):
            q.perguntas.append(pergunta)

    return aplicar


@_executor(Passo.reenviar)
@trace("reenviar")
def _executar_reenviar(p: Processo, arquivos: Arquivos) -> Aplicar:
    ev = _pendencia_aberta(p)
    resposta = next(
        (q.resposta for q in p.perguntas if q.id == _id_pendencia(ev) and q.resposta),
        None,
    )
    correcao = resposta or ev.correcao_proposta
    novo = portal.reenviar(p.numero_solicitacao, correcao)
    registrar_uso(decisao=f"Documentação reenviada ao portal: {correcao}")

    def aplicar(q: Processo) -> None:
        _aplicar_eventos(q, [*q.eventos, novo])
        for x in q.perguntas:
            if x.id == _id_pendencia(ev) and not x.resposta:
                x.resposta = f"Reenviado ao portal: {correcao}"
                x.respondida_em = repo.agora()

    return aplicar


# --- decisão do próximo passo ----------------------------------------------------------


def _resumo_para_decisao(p: Processo, opcoes: list[Passo]) -> str:
    resumo = {
        "etapa": p.etapa.value,
        "campos_da_conta": sorted(p.campos),
        "tem_kit": p.kit is not None,
        "documentos": len(p.documentos),
        "perguntas_abertas": sum(1 for q in p.perguntas if not q.resposta),
        "regras": {r.regra_id: r.status.value for r in p.regras},
        "protocolado": p.numero_solicitacao is not None,
        "passos_disponiveis": {o.value: _DESCRICAO[o] for o in opcoes},
    }
    return json.dumps(resumo, ensure_ascii=False)


@trace("decidir_proximo_passo")
def _decidir(p: Processo, opcoes: list[Passo], quem: str = "sem_modelo") -> Passo:
    """Execução determinística: opção única, sem modelo de decisão ou modelo que não avançou."""
    quem = "unica_opcao" if len(opcoes) == 1 else quem
    registrar_uso(decisao=f"{opcoes[0].value} ({quem}): {_DESCRICAO[opcoes[0]]}")
    return opcoes[0]


@trace("decidir_proximo_passo")
def _registrar_decisao_sdk(passo: Passo, motivo: str) -> None:
    registrar_uso(decisao=f"{passo.value} (vercel_ai_sdk): {motivo}")


def _registrar_uso_sdk(processo_id: str, params: dict) -> None:
    entrada, saida = params["inputTokens"], params["outputTokens"]
    gravar_passo(
        PassoTrace(
            processo_id=processo_id,
            passo="modelo_agente_ai_sdk",
            tokens_entrada=entrada,
            tokens_saida=saida,
            ms=params.get("ms", 0),
            custo_brl=custo_por_tokens(entrada, saida),
            em=repo.agora(),
            decisao=f"Vercel AI SDK: {params['model']}",
        )
    )


def _laco_sdk(processo_id: str) -> bool:
    """Rodada com o modelo de decisão. Devolve False quando o agente falhou: a
    falha vai para o trace e o laço segue pela ordem padrão, sem prender o
    processo numa pendência que ninguém consegue resolver."""
    # Uma nova tentativa precisa liberar a falha anterior para alcançar a revisão.
    repo.atualizar(
        processo_id,
        lambda q: setattr(
            q, "perguntas", [x for x in q.perguntas if x.id != "falha:agente_ai_sdk"]
        ),
    )
    execucoes = 0

    def estado() -> dict:
        p = repo.carregar(processo_id)
        opcoes = passos_disponiveis(
            p, repo.arquivos(processo_id), repo.memoria(processo_id)
        )
        return {
            "options": [o.value for o in opcoes],
            "summary": json.loads(_resumo_para_decisao(p, opcoes)),
        }

    def atender(method: str, params: dict) -> dict:
        nonlocal execucoes
        if method == "state":
            return estado()
        if method == "usage":
            _registrar_uso_sdk(processo_id, params)
            return {}
        if method != "execute":
            raise ValueError("Método desconhecido")
        passo = Passo(params["name"])
        p, arquivos, memoria = (
            repo.carregar(processo_id),
            repo.arquivos(processo_id),
            repo.memoria(processo_id),
        )
        if execucoes >= MAX_PASSOS or passo not in passos_disponiveis(
            p, arquivos, memoria
        ):
            raise ValueError("Passo não autorizado pelo estado atual")
        execucoes += 1
        _registrar_decisao_sdk(passo, params["motivo"])
        _rodar(processo_id, passo, p, arquivos, memoria)
        atualizado = repo.carregar(processo_id)
        falhou = any(
            q.id == f"falha:{passo}" and not q.resposta for q in atualizado.perguntas
        )
        return {"ok": not falhou, "state": estado()}

    try:
        ai_sdk.run(
            {
                "mode": "agent",
                "models": llm._modelos("decisao"),
                "tools": {p.value: d for p, d in _DESCRICAO.items()},
                "maxSteps": MAX_PASSOS,
            },
            atender,
        )
    except ai_sdk.SDKError as exc:
        gravar_passo(
            PassoTrace(
                processo_id=processo_id,
                passo="modelo_agente_ai_sdk",
                em=repo.agora(),
                erro=f"SDKError: {exc}"[:500],
                decisao="Agente de decisão não concluiu; o processo segue pela ordem padrão.",
            )
        )
        ok = False
    else:
        ok = True
    repo.atualizar(
        processo_id,
        lambda q: setattr(
            q,
            "perguntas",
            [x for x in q.perguntas if x.id != "falha:agente_ai_sdk"],
        ),
    )
    return ok


# --- laço ---------------------------------------------------------------------------------

_SEM_NOVA_TENTATIVA = (portal.PortalErro, ValueError, llm.LLMIndisponivel)


def _com_tentativas(passo: Passo, p: Processo, arquivos: Arquivos) -> Aplicar:
    espera = float(os.environ.get("ORQUESTRADOR_ESPERA_S", "0.5"))
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            return _EXECUTORES[passo](p, arquivos)
        except _SEM_NOVA_TENTATIVA:
            raise
        except Exception:
            if tentativa == TENTATIVAS:
                raise
            time.sleep(espera * tentativa)
    raise AssertionError("inalcançável")


def _consolidar(
    processo_id: str, passo: Passo, antes: str | None, aplicar: Aplicar
) -> None:
    """Aplica o resultado sob a trava do processo. Se as entradas mudaram desde
    o retrato, o resultado é descartado e a memória guarda o hash antigo, o que
    deixa o passo pendente para rodar de novo."""

    def mudar(q: Processo) -> None:
        arquivos = repo.arquivos(processo_id)
        memoria = repo.memoria(processo_id)
        dia = hoje()
        inalterado = _ENTRADAS[passo](Estado(q, arquivos, memoria, dia)) == antes
        if inalterado:
            aplicar(q)
            q.perguntas = [
                x
                for x in q.perguntas
                if not (x.id == f"falha:{passo}" and not x.resposta)
            ]
            depois = _ENTRADAS[passo](Estado(q, arquivos, memoria, dia))
        else:
            depois = antes
        repo.marcar(processo_id, passo, depois or "")

    repo.atualizar(processo_id, mudar)


def _contexto_da_falha(passo: Passo, p: Processo, arquivos: Arquivos) -> str:
    enviados = [
        a.name for t in _TIPOS_DO_PASSO.get(passo, ()) for a in arquivos.get(t, [])
    ]
    if enviados:
        return "os arquivos " + ", ".join(enviados)
    return f"o processo {p.id} na etapa {p.etapa.value}"


def _registrar_falha(
    processo_id: str, passo: Passo, antes: str | None, erro: Exception, contexto: str
) -> None:
    pergunta = Pergunta(
        id=f"falha:{passo}",
        campo=f"falha:{passo}",
        destinatario="engenheiro",
        texto=(
            f"O passo '{passo}' falhou ao tratar {contexto}. Último erro: "
            f"{type(erro).__name__}: {erro}. Os outros passos seguem. Depois de corrigir a "
            "causa, peça para rodar de novo ou envie um arquivo novo."
        ),
    )

    def mudar(q: Processo) -> None:
        q.perguntas = [x for x in q.perguntas if x.id != pergunta.id]
        q.perguntas.append(pergunta)
        repo.marcar(processo_id, passo, antes or "")

    repo.atualizar(processo_id, mudar)


def _rodar(
    processo_id: str,
    passo: Passo,
    p: Processo,
    arquivos: Arquivos,
    memoria: dict[str, str],
) -> None:
    antes = _ENTRADAS[passo](Estado(p, arquivos, memoria, hoje()))
    try:
        aplicar = _com_tentativas(passo, p, arquivos)
        _consolidar(processo_id, passo, antes, aplicar)
    except Exception as exc:  # noqa: BLE001 - uma ferramenta que falha não derruba o processo
        _registrar_falha(
            processo_id, passo, antes, exc, _contexto_da_falha(passo, p, arquivos)
        )


def trabalhando(p: Processo) -> bool:
    """Há passo do agente a rodar agora (montando o pacote, ou protocolando o que o
    engenheiro acabou de assinar): a tela mostra espera e se atualiza."""
    assinado = p.etapa == Etapa.EM_REVISAO and p.revisado_por
    if p.etapa != Etapa.MONTAGEM and not assinado:
        return False
    return bool(passos_disponiveis(p, repo.arquivos(p.id), repo.memoria(p.id)))


def _estado_atual(
    processo_id: str,
) -> tuple[Processo, Arquivos, dict[str, str], list[Passo]]:
    p = repo.carregar(processo_id)
    arquivos = repo.arquivos(processo_id)
    memoria = repo.memoria(processo_id)
    return p, arquivos, memoria, passos_disponiveis(p, arquivos, memoria)


def _laco(processo_id: str) -> None:
    usar_sdk = True  # depois de uma falha do agente, a rodada segue na ordem padrão
    for _ in range(MAX_PASSOS):
        p, arquivos, memoria, opcoes = _estado_atual(processo_id)
        if not opcoes:
            return
        quem = "sem_modelo"
        if len(opcoes) > 1 and usar_sdk and llm.disponivel("decisao"):
            quem = "ordem_padrao"
            usar_sdk = _laco_sdk(processo_id)
            if usar_sdk and repo.memoria(processo_id) != memoria:
                continue
            # O modelo falhou ou não executou nenhum passo: a ordem padrão garante que o processo anda.
            p, arquivos, memoria, opcoes = _estado_atual(processo_id)
            if not opcoes:
                return
        passo = _decidir(p, opcoes, quem)
        _rodar(processo_id, passo, p, arquivos, memoria)


_mutex = threading.Lock()
_ocupados: set[str] = set()
_repetir: set[str] = set()


def _entrar(processo_id: str) -> bool:
    with _mutex:
        if processo_id in _ocupados:
            _repetir.add(processo_id)
            return False
        _ocupados.add(processo_id)
        return True


def _sair(processo_id: str) -> bool:
    """True se chegou pedido enquanto rodava: o dono refaz a volta."""
    with _mutex:
        if processo_id in _repetir:
            _repetir.discard(processo_id)
            return True
        _ocupados.discard(processo_id)
        return False


def orquestrar(processo_id: str) -> Processo:
    """Recebe "homologar este sistema" e leva o processo até onde as guardas
    deixam. Se já há uma execução em andamento para o processo, só pede uma volta
    extra a ela e devolve o estado atual."""
    repo.carregar(processo_id)
    if not _entrar(processo_id):
        return repo.carregar(processo_id)
    try:
        with processo_atual(processo_id):
            while True:
                _laco(processo_id)
                if not _sair(processo_id):
                    break
    except BaseException:
        with _mutex:
            _ocupados.discard(processo_id)
            _repetir.discard(processo_id)
        raise
    return repo.carregar(processo_id)


def sincronizar_portal(processo_id: str) -> Processo:
    """Consulta o portal agora e grava eventos, etapa e prazos. Usado depois de
    uma ação do integrador no portal, que muda a etapa sem mudar o relógio."""
    p = repo.carregar(processo_id)
    estado = Estado(p, {}, {}, hoje())
    antes = _ENTRADAS[Passo.consultar_portal](estado)
    with processo_atual(processo_id):
        aplicar = _executar_consultar_portal(p, {})
        _consolidar(processo_id, Passo.consultar_portal, antes, aplicar)
    return repo.carregar(processo_id)
