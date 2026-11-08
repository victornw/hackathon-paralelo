"""Aplicação FastAPI: painel do Dev B (HTML) e API JSON do agente em /api.

    uvicorn app.main:app

As ações que a lei reserva a uma pessoa ficam na API: o engenheiro aprova a
revisão e o integrador age no portal (aprovar orçamento, pedir vistoria). O
agente só prepara, lembra e, depois da aprovação, protocola e reenvia.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.core import orquestrador
from app.core import regras as conferidor
from app.core import repositorio as repo
from app.core.aprovacao import bloqueios_aprovacao
from app.core.orquestrador import FONTE_RESPOSTA
from app.portal_sim import portal
from app.portal_sim.relogio import avancar_tempo
from app.schemas import (
    CampoExtraido,
    Carga,
    Etapa,
    Fonte,
    PassoTrace,
    Processo,
    StringFV,
)
from app.tracing import listar_passos, resumo_custo
from app.web import painel

# --- respostas do integrador que viram dado do processo ----------------------------------


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower().strip()


def _afirmativa(texto: str) -> bool:
    primeira = (_normalizar(texto).split() or [""])[0].strip(".,!;")
    return primeira in {
        "sim",
        "s",
        "ok",
        "confirmo",
        "confirmado",
        "correto",
        "certo",
        "isso",
        "yes",
    }


def _numero(texto: str) -> float | int:
    achado = re.search(r"-?\d+(?:[.,]\d+)?", texto)
    if achado is None:
        raise ValueError(f"Não encontrei um número em '{texto}'.")
    valor = float(achado.group().replace(",", "."))
    return int(valor) if valor.is_integer() else valor


def _tipo_ramal(texto: str) -> str:
    normal = _normalizar(texto)
    for valor in ("aereo", "subterraneo"):
        if valor in normal:
            return valor
    raise ValueError("Responda 'aéreo' ou 'subterrâneo'.")


def _tipo_ligacao(texto: str) -> str:
    normal = _normalizar(texto)
    for prefixo, valor in (
        ("mono", "monofasico"),
        ("bi", "bifasico"),
        ("tri", "trifasico"),
    ):
        if prefixo in normal:
            return valor
    raise ValueError("Responda 'monofásico', 'bifásico' ou 'trifásico'.")


def _email(texto: str) -> str:
    email = texto.strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError(f"E-mail inválido: '{texto}'.")
    return email


def _coordenadas(texto: str) -> tuple[float, float]:
    numeros = re.findall(r"-?\d+(?:[.,]\d+)?", texto)
    if len(numeros) != 2:
        raise ValueError(
            "Informe latitude e longitude em graus decimais, ex.: -3,7319, -38,5267."
        )
    return tuple(float(n.replace(",", ".")) for n in numeros)


def _potencia_w(numero: str, unidade: str) -> float:
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", numero):
        valor = float(numero.replace(".", ""))
    else:
        valor = float(numero.replace(",", "."))
    return valor * 1000 if unidade.lower() == "kw" else valor


_LINHA_CARGA = re.compile(
    r"^(?P<descricao>.+?)\s+(?P<potencia>\d+(?:[.,]\d+)*)\s*(?P<unidade>kw|w)?"
    r"(?:\s*[x×]\s*(?P<quantidade>\d+))?$",
    re.IGNORECASE,
)


def _cargas(texto: str) -> list[Carga]:
    """Aceita uma linha por carga ("ar-condicionado 1400 W x2") ou uma lista JSON."""
    if texto.lstrip().startswith("["):
        try:
            return [Carga.model_validate(c) for c in json.loads(texto)]
        except ValueError as exc:
            raise ValueError(f"Lista de cargas inválida: {exc}") from exc
    cargas = []
    for linha in filter(None, (l.strip() for l in texto.splitlines())):
        achado = _LINHA_CARGA.match(linha)
        if achado is None:
            raise ValueError(
                f"Não entendi a carga '{linha}'. Use: descrição potência em W e xquantidade."
            )
        cargas.append(
            Carga(
                descricao=achado["descricao"].strip(" -:;"),
                potencia_w=_potencia_w(achado["potencia"], achado["unidade"] or "w"),
                quantidade=int(achado["quantidade"] or 1),
            )
        )
    if not cargas:
        raise ValueError("A relação de cargas veio vazia.")
    return cargas


def _confirmado(valor: str | float, trecho: str) -> CampoExtraido:
    return CampoExtraido(
        valor=valor, confianca=1, fonte=Fonte(documento=FONTE_RESPOSTA, trecho=trecho)
    )


def _exigir_kit(p: Processo) -> None:
    if p.kit is None:
        raise ValueError("O kit ainda não foi lido; envie a proposta e os datasheets.")


Aplicador = Callable[[Processo, str], None]


def _visita_confirmada(nome: str, parser: Callable[[str], float | int]) -> Aplicador:
    return lambda p, t: setattr(p.visita, nome, _confirmado(parser(t), t))


def _visita_simples(nome: str, parser: Callable[[str], object]) -> Aplicador:
    return lambda p, t: setattr(p.visita, nome, parser(t))


def _conta(chave: str, parser: Callable[[str], str | float | int]) -> Aplicador:
    """Resposta afirmativa confirma o valor lido (confiança 1); qualquer outra é o valor certo."""

    def aplicar(p: Processo, texto: str) -> None:
        atual = p.campos.get(chave)
        if _afirmativa(texto):
            if atual is None or atual.valor is None:
                raise ValueError("Não há valor lido para confirmar; informe o valor.")
            valor = atual.valor
        else:
            valor = parser(texto)
        p.campos[chave] = _confirmado(valor, texto)

    return aplicar


def _definir_coordenadas(p: Processo, texto: str) -> None:
    p.visita.latitude, p.visita.longitude = _coordenadas(texto)


def _definir_email(p: Processo, texto: str) -> None:
    p.email_contato = _email(texto)


def _definir_cargas(p: Processo, texto: str) -> None:
    p.visita.relacao_cargas = _cargas(texto)


def _definir_strings(p: Processo, texto: str) -> None:
    """Confirma as strings sugeridas ("sim") ou define os módulos em série por MPPT na ordem."""
    _exigir_kit(p)
    if _afirmativa(texto) and p.kit.strings:
        for s in p.kit.strings:
            s.sugerida = False
        return
    quantidades = [
        int(n)
        for n in re.findall(
            r"\d+", re.sub(r"mppt\s*\d+", "", texto, flags=re.IGNORECASE)
        )
    ]
    if not quantidades or 0 in quantidades:
        raise ValueError(
            "Responda 'sim' para confirmar, ou os módulos em série por MPPT, ex.: 'MPPT1: 7, MPPT2: 6'."
        )
    p.kit.strings = [
        StringFV(mppt=i, modulos_em_serie=n) for i, n in enumerate(quantidades, 1)
    ]


def _definir_coef_temp(p: Processo, texto: str) -> None:
    _exigir_kit(p)
    valor = float(_numero(texto))
    if valor > 0:
        raise ValueError(
            "O coeficiente do Voc é negativo; informe com sinal, ex.: -0,27."
        )
    p.kit.modulo.coef_temp_voc_pct_c = valor


_AREAS = {
    "ceara": "ceara",
    "sao paulo": "sao_paulo",
    "rj serra": "rj_serra",
    "rj sul fluminense": "rj_sul_fluminense",
    "sul fluminense": "rj_sul_fluminense",
    "rj demais areas": "rj_demais",
    "rj demais": "rj_demais",
}


def _definir_area(p: Processo, texto: str) -> None:
    import unicodedata

    chave = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    chave = " ".join(chave.lower().replace("-", " ").replace("_", " ").split())
    if chave not in _AREAS:
        raise ValueError(
            "Responda com uma das áreas: Ceará, São Paulo, RJ Serra, "
            "RJ Sul Fluminense ou RJ demais áreas."
        )
    p.visita.area_concessao = _AREAS[chave]


def _definir_inmetro(p: Processo, texto: str) -> None:
    _exigir_kit(p)
    p.kit.inversor.certificado_inmetro = texto.strip()


_CHAVES_DA_CONTA: dict[str, Callable[[str], str | float | int]] = {
    "uc": str.strip,
    "titular": str.strip,
    "cpf_cnpj": str.strip,
    "endereco": str.strip,
    "cidade": str.strip,
    "classe": str.strip,
    "subgrupo": str.strip,
    "tipo_ligacao": _tipo_ligacao,
    "tensao_atendimento_v": _numero,
    "consumo_medio_kwh": _numero,
}

RESPOSTAS: dict[str, Aplicador] = {
    **{
        f"campos.{chave}": _conta(chave, parser)
        for chave, parser in _CHAVES_DA_CONTA.items()
    },
    "disjuntor_padrao_a": _visita_confirmada("disjuntor_padrao_a", _numero),
    "polos_padrao": _visita_confirmada("polos_padrao", _numero),
    "bitola_ca_mm2": _visita_simples("bitola_ca_mm2", _numero),
    "distancia_inversor_quadro_m": _visita_simples(
        "distancia_inversor_quadro_m", _numero
    ),
    "latitude": _visita_simples("latitude", _numero),
    "longitude": _visita_simples("longitude", _numero),
    "coordenadas_padrao": _definir_coordenadas,
    "tipo_ramal": _visita_simples("tipo_ramal", _tipo_ramal),
    "email_contato": _definir_email,
    "relacao_cargas": _definir_cargas,
    "strings": _definir_strings,
    "coef_temp_voc_pct_c": _definir_coef_temp,
    "certificado_inmetro": _definir_inmetro,
    "area_concessao": _definir_area,
}

# --- API --------------------------------------------------------------------------------

api = APIRouter(prefix="/api")


class NovoProcesso(BaseModel):
    email_contato: str | None = None


class Resposta(BaseModel):
    id: str
    resposta: str = Field(min_length=1)


class Revisao(BaseModel):
    engenheiro: str = Field(min_length=1)


class AvancoRelogio(BaseModel):
    dias: int = Field(ge=1)


@api.post("/processos", status_code=201)
def criar_processo(corpo: NovoProcesso | None = None) -> Processo:
    return repo.criar(corpo.email_contato if corpo else None)


@api.get("/processos")
def listar_processos() -> list[Processo]:
    return repo.listar()


@api.get("/processos/{processo_id}")
def obter_processo(processo_id: str) -> Processo:
    return repo.carregar(processo_id)


@api.post("/processos/{processo_id}/arquivos")
def enviar_arquivo(
    processo_id: str,
    fundo: BackgroundTasks,
    tipo: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> dict[str, str]:
    p = repo.carregar(processo_id)
    if p.etapa not in (Etapa.MONTAGEM, Etapa.EM_REVISAO):
        raise HTTPException(
            409,
            f"O processo já está em '{p.etapa.value}'; arquivos novos não entram mais no pacote.",
        )
    try:
        caminho = repo.guardar_arquivo(
            processo_id, tipo, file.filename or "", file.file.read()
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if p.etapa == Etapa.EM_REVISAO:
        _invalidar_revisao(processo_id)
    fundo.add_task(orquestrador.orquestrar, processo_id)
    return {"caminho": str(caminho)}


def _invalidar_revisao(processo_id: str) -> None:
    """Dado novo depois da revisão: o pacote volta para a montagem e o engenheiro revisa de novo."""

    def mudar(q: Processo) -> None:
        if q.etapa == Etapa.EM_REVISAO:
            q.etapa = Etapa.MONTAGEM
            q.revisado_por = None
            q.revisado_em = None

    repo.atualizar(processo_id, mudar)


@api.post("/processos/{processo_id}/respostas")
def responder(
    processo_id: str, respostas: list[Resposta], fundo: BackgroundTasks
) -> Processo:
    p = repo.carregar(processo_id)
    conhecidas = {q.id for q in p.perguntas}
    desconhecidas = [r.id for r in respostas if r.id not in conhecidas]
    if desconhecidas:
        raise HTTPException(
            404, f"Perguntas não encontradas: {', '.join(desconhecidas)}."
        )

    def mudar(q: Processo) -> None:
        for resposta in respostas:
            pergunta = next(x for x in q.perguntas if x.id == resposta.id)
            aplicar = RESPOSTAS.get(pergunta.campo)
            if aplicar:
                aplicar(q, resposta.resposta)
            pergunta.resposta = resposta.resposta
            pergunta.respondida_em = repo.agora()
        # Toda resposta pode entrar nos documentos (ex.: DPS no memorial): na revisão,
        # o pacote volta para a montagem e é gerado e conferido de novo.
        mudou = any(not r.id.startswith("falha:") for r in respostas)
        if mudou and q.etapa == Etapa.EM_REVISAO:
            q.etapa = Etapa.MONTAGEM
            q.revisado_por = None
            q.revisado_em = None

    try:
        atualizado = repo.atualizar(processo_id, mudar)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    fundo.add_task(orquestrador.orquestrar, processo_id)
    return atualizado


@api.post("/processos/{processo_id}/rodar", status_code=202)
def rodar(
    processo_id: str, fundo: BackgroundTasks, refazer: bool = False
) -> dict[str, str]:
    """`refazer` libera os passos que falharam (têm pergunta `falha:` aberta) para nova tentativa."""
    p = repo.carregar(processo_id)
    if refazer:
        for q in p.perguntas:
            if q.id.startswith("falha:") and not q.resposta:
                repo.esquecer(processo_id, q.id.removeprefix("falha:"))
    fundo.add_task(orquestrador.orquestrar, processo_id)
    return {"status": "aceito"}


@api.post("/processos/{processo_id}/revisao")
def revisar(processo_id: str, corpo: Revisao, fundo: BackgroundTasks) -> Processo:
    bloqueios: list[str] = []

    def mudar(q: Processo) -> None:
        if q.etapa not in (Etapa.EM_REVISAO, Etapa.PENDENCIA):
            raise HTTPException(
                409, f"Não há revisão a fazer na etapa '{q.etapa.value}'."
            )
        bloqueios.extend(bloqueios_aprovacao(q))
        if not bloqueios:
            # Releitura e recálculo sob a trava: aprovação não usa só o cache.
            q.regras = conferidor.conferir(q)
            bloqueios.extend(bloqueios_aprovacao(q))
        if bloqueios:
            q.revisado_por = None
            q.revisado_em = None
            return
        q.revisado_por = corpo.engenheiro.strip()
        q.revisado_em = repo.agora()

    atualizado = repo.atualizar(processo_id, mudar)
    if bloqueios:
        raise HTTPException(
            409, "Pacote não pode ser aprovado: " + "; ".join(bloqueios)
        )

    fundo.add_task(orquestrador.orquestrar, processo_id)
    return atualizado


def _acao_do_integrador(
    processo_id: str, acao: Callable[[str], object], fundo: BackgroundTasks
) -> Processo:
    p = repo.carregar(processo_id)
    if not p.numero_solicitacao:
        raise HTTPException(409, "O processo ainda não foi protocolado.")
    try:
        acao(p.numero_solicitacao)
    except portal.SolicitacaoNaoEncontrada as exc:
        raise HTTPException(404, str(exc)) from exc
    except portal.PortalErro as exc:
        raise HTTPException(409, str(exc)) from exc
    atualizado = orquestrador.sincronizar_portal(processo_id)
    fundo.add_task(orquestrador.orquestrar, processo_id)
    return atualizado


@api.post("/processos/{processo_id}/portal/aprovar-orcamento")
def aprovar_orcamento(processo_id: str, fundo: BackgroundTasks) -> Processo:
    return _acao_do_integrador(processo_id, portal.aprovar_orcamento, fundo)


@api.post("/processos/{processo_id}/portal/solicitar-vistoria")
def solicitar_vistoria(processo_id: str, fundo: BackgroundTasks) -> Processo:
    return _acao_do_integrador(processo_id, portal.solicitar_vistoria, fundo)


@api.post("/relogio/avancar")
def avancar_relogio(corpo: AvancoRelogio, fundo: BackgroundTasks) -> dict[str, str]:
    """Avança o relógio simulado; a distribuidora simulada dá um passo do roteiro em cada
    processo protocolado e o agente roda de novo em todos os que não terminaram."""
    dia = avancar_tempo(corpo.dias)
    for p in repo.listar():
        if p.etapa == Etapa.CONCLUIDO:
            continue
        if p.numero_solicitacao:
            try:
                portal.avancar_distribuidora(p.numero_solicitacao)
            except portal.PortalErro:
                pass  # a bola está com o integrador
        fundo.add_task(orquestrador.orquestrar, p.id)
    return {"hoje": dia.isoformat()}


@api.get("/processos/{processo_id}/documentos/{nome}")
def baixar_documento(processo_id: str, nome: str) -> FileResponse:
    documento = next(
        (d for d in repo.carregar(processo_id).documentos if d.nome_arquivo == nome),
        None,
    )
    if documento is None or not Path(documento.caminho).is_file():
        raise HTTPException(404, "Documento não encontrado.")
    return FileResponse(documento.caminho, filename=documento.nome_arquivo)


@api.get("/processos/{processo_id}/trace")
def trace_do_processo(processo_id: str) -> dict[str, object]:
    repo.carregar(processo_id)
    passos: list[PassoTrace] = listar_passos(processo_id)
    return {"passos": passos, "resumo_custo": asdict(resumo_custo(processo_id))}


# --- aplicação ----------------------------------------------------------------------------


@asynccontextmanager
async def _ao_subir(_app: FastAPI):
    """Plano grátis do Render não tem disco: o banco começa vazio a cada deploy
    ou reinício. Os casos prontos da demonstração são recriados na hora."""
    try:
        from app.portal_sim.demo import garantir_demo

        garantir_demo()
    except Exception:  # a demo nunca impede o site de subir
        logging.getLogger(__name__).exception(
            "Não foi possível recriar os casos prontos."
        )
    yield


app = FastAPI(title="Agente de homologação solar", lifespan=_ao_subir)
app.include_router(painel.router)
app.include_router(api)
app.mount(
    "/static",
    StaticFiles(directory=Path(painel.__file__).parent / "static"),
    name="static",
)


@app.exception_handler(repo.ProcessoNaoEncontrado)
def _processo_nao_encontrado(
    _: Request, __: repo.ProcessoNaoEncontrado
) -> JSONResponse:
    return JSONResponse({"detail": "Processo não encontrado."}, status_code=404)


@app.get("/", include_in_schema=False)
def raiz() -> RedirectResponse:
    return RedirectResponse("/painel")
