"""Telas do Portal GD simulado (/portal-gd). Nunca acessa o portal real.

Os templates ficam em app/web/templates/portal/. Este módulo não importa
app.web.painel (que inclui este router), então não há import circular.
"""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.portal_sim import portal
from app.portal_sim.portal import PortalErro, SolicitacaoNaoEncontrada
from app.portal_sim.relogio import hoje
from app.schemas import Etapa

log = logging.getLogger(__name__)
router = APIRouter(prefix="/portal-gd")
templates = Jinja2Templates(
    directory=Path(__file__).resolve().parents[1] / "web" / "templates"
)

MSG_NAO_ENCONTRADA = (
    "Solicitação não encontrada. Confira o código da UC, o e-mail e o número."
)

ROTULOS = {
    Etapa.MONTAGEM: "Montagem",
    Etapa.EM_REVISAO: "Em revisão",
    Etapa.PROTOCOLADO: "Protocolado",
    Etapa.PENDENCIA: "Pendência",
    Etapa.ORCAMENTO_EMITIDO: "Orçamento emitido",
    Etapa.ORCAMENTO_APROVADO: "Orçamento aprovado",
    Etapa.VISTORIA_SOLICITADA: "Vistoria solicitada",
    Etapa.VISTORIA: "Vistoria",
    Etapa.MEDIDOR: "Medidor",
    Etapa.CONCLUIDO: "Concluído",
}
PASSOS = [
    Etapa.PROTOCOLADO,
    Etapa.PENDENCIA,
    Etapa.ORCAMENTO_EMITIDO,
    Etapa.ORCAMENTO_APROVADO,
    Etapa.VISTORIA_SOLICITADA,
    Etapa.VISTORIA,
    Etapa.MEDIDOR,
    Etapa.CONCLUIDO,
]

# (campo, rótulo, unidade)
CAMPOS_FORMULARIO = [
    ("codigo_uc", "Código da UC", ""),
    ("classe", "Classe", ""),
    ("titular", "Titular", ""),
    ("email", "E-mail", ""),
    ("endereco", "Endereço", ""),
    ("cpf_cnpj", "CPF ou CNPJ", ""),
    ("telefone", "Telefone", ""),
    ("fonte", "Fonte de geração", ""),
    ("potencia_instalada_geracao_kw", "Potência instalada de geração", "kW"),
    ("tipo_geracao", "Tipo de geração", ""),
    ("qtd_ucs_credito", "Quantidade de UCs para crédito", ""),
    ("data_implantacao", "Data de implantação", ""),
    ("potencia_instalada_uc_kw", "Carga instalada da UC", "kW"),
    ("nivel_tensao", "Nível de tensão", ""),
    ("tipo_conexao", "Tipo de conexão", ""),
    ("tensao_atendimento_v", "Tensão de atendimento", "V"),
    ("corrente_disjuntor_a", "Corrente do disjuntor", "A"),
    ("tipo_ramal", "Tipo de ramal", ""),
    ("subgrupo", "Subgrupo", ""),
    ("modalidade", "Modalidade de compensação", ""),
    ("demanda_kw", "Demanda", "kW"),
    ("latitude", "Latitude", ""),
    ("longitude", "Longitude", ""),
]

ACOES = {
    "reenviar": (Etapa.PENDENCIA, portal.reenviar),
    "aprovar-orcamento": (Etapa.ORCAMENTO_EMITIDO, portal.aprovar_orcamento),
    "solicitar-vistoria": (Etapa.ORCAMENTO_APROVADO, portal.solicitar_vistoria),
}


def _data_br(d) -> str:
    return d.strftime("%d/%m/%Y")


def _numero_br(v: float) -> str:
    texto = f"{v:,.6f}".rstrip("0").rstrip(".")
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _valor(v, unidade: str) -> str:
    if v is None or v == "":
        return "—"
    if hasattr(v, "strftime"):
        return _data_br(v)
    if isinstance(v, float):
        v = _numero_br(v)
    return f"{v} {unidade}".strip()


templates.env.filters["data_br"] = _data_br


def _linhas_formulario(numero: str) -> list[tuple[str, str]]:
    dados = portal.formulario(numero).model_dump()
    return [(rot, _valor(dados.get(campo), un)) for campo, rot, un in CAMPOS_FORMULARIO]


def _passos(eventos) -> list[dict]:
    atual = eventos[-1].etapa
    ocorridas = {e.etapa for e in eventos}
    saida = []
    reenviado = atual == Etapa.PROTOCOLADO and Etapa.PENDENCIA in ocorridas
    for etapa in PASSOS:
        if etapa == Etapa.PENDENCIA and etapa not in ocorridas:
            continue
        if etapa == atual and not reenviado:
            estado = "atual"
        elif etapa in ocorridas:
            estado = "feito"
        else:
            estado = "futuro"
        saida.append({"rotulo": ROTULOS[etapa], "estado": estado})
        if reenviado and etapa == Etapa.PENDENCIA:
            # depois do reenvio a solicitação volta para análise, à frente da pendência
            saida.append({"rotulo": "Reenviado, em análise", "estado": "atual"})
    return saida


def _url_consulta(uc: str, email: str, numero: str) -> str:
    return "/portal-gd/consulta?" + urlencode(
        {"uc": uc, "email": email, "numero": numero}
    )


def _sincronizar(numero: str) -> None:
    """Atualiza o Processo correspondente. Se app.core falhar, o portal segue."""
    try:
        from app.core import orquestrador
        from app.core import repositorio as repo

        for p in repo.listar():
            if p.numero_solicitacao == numero:
                orquestrador.sincronizar_portal(p.id)
    except Exception:
        log.warning(
            "Falha ao sincronizar o processo do portal %s", numero, exc_info=True
        )


def _consulta(
    request: Request,
    uc: str,
    email: str,
    numero: str,
    erro: str | None = None,
    status_code: int = 200,
):
    uc, email, numero = uc.strip(), email.strip(), numero.strip()
    contexto = {"uc": uc, "email": email, "numero": numero, "erro": erro}
    try:
        if not (uc and email and numero):
            raise SolicitacaoNaoEncontrada(MSG_NAO_ENCONTRADA)
        eventos = portal.consultar_status(uc, email, numero)
    except SolicitacaoNaoEncontrada:
        contexto["erro"] = MSG_NAO_ENCONTRADA
        contexto["encontrada"] = False
        return templates.TemplateResponse(
            request,
            "portal/consulta.html",
            contexto,
            status_code=404 if status_code == 404 else 200,
        )
    atual = eventos[-1].etapa
    contexto.update(
        encontrada=True,
        eventos=eventos,
        etapa_rotulo=ROTULOS[atual],
        etapa=atual,
        passos=_passos(eventos),
        formulario=_linhas_formulario(numero),
        rotulos=ROTULOS,
        Etapa=Etapa,
    )
    return templates.TemplateResponse(
        request, "portal/consulta.html", contexto, status_code=status_code
    )


@router.get("")
def inicio(request: Request):
    return templates.TemplateResponse(request, "portal/inicio.html", {})


@router.get("/consulta")
def consulta(request: Request, uc: str = "", email: str = "", numero: str = ""):
    if not (uc or email or numero):
        return templates.TemplateResponse(
            request,
            "portal/consulta.html",
            {"uc": "", "email": "", "numero": "", "erro": None, "encontrada": False},
        )
    return _consulta(request, uc, email, numero)


@router.post("/acoes/{acao}")
def acao(
    request: Request,
    acao: str,
    uc: str = Form(""),
    email: str = Form(""),
    numero: str = Form(""),
    correcao: str = Form(""),
):
    if acao not in ACOES:
        return templates.TemplateResponse(
            request,
            "portal/consulta.html",
            {
                "uc": uc,
                "email": email,
                "numero": numero,
                "erro": "Ação desconhecida.",
                "encontrada": False,
            },
            status_code=404,
        )
    uc, email, numero = uc.strip(), email.strip(), numero.strip()
    try:
        portal.consultar_status(uc, email, numero)
    except SolicitacaoNaoEncontrada:
        return _consulta(request, uc, email, numero, status_code=404)
    try:
        if acao == "reenviar":
            if not correcao.strip():
                raise PortalErro("Descreva a correção antes de reenviar.")
            ACOES[acao][1](numero, correcao.strip())
        else:
            ACOES[acao][1](numero)
    except PortalErro as e:
        return _consulta(request, uc, email, numero, erro=str(e))
    _sincronizar(numero)
    return RedirectResponse(_url_consulta(uc, email, numero), status_code=303)


@router.get("/operador")
def operador(request: Request, aguardando: str = "", reiniciado: str = ""):
    linhas = [
        {"r": r, "url": _url_consulta(r.uc, r.email, r.numero)}
        for r in portal.listar_solicitacoes()
    ]
    return templates.TemplateResponse(
        request,
        "portal/operador.html",
        {
            "hoje": hoje(),
            "linhas": linhas,
            "rotulos": ROTULOS,
            "aguardando": aguardando,
            "reiniciado": reiniciado,
            "data_demo": _data_demo(),
        },
    )


def _data_demo():
    from app.portal_sim.demo import data_demo

    return data_demo()


@router.post("/operador/reiniciar")
def reiniciar():
    """Recria os casos da demonstração e volta o relógio para a data da demo."""
    from app.portal_sim.demo import reiniciar_demo

    reiniciar_demo()
    return RedirectResponse("/portal-gd/operador?reiniciado=1", status_code=303)


@router.post("/operador/{numero}/avancar")
def avancar(numero: str):
    try:
        portal.avancar_distribuidora(numero)
    except SolicitacaoNaoEncontrada:
        return RedirectResponse("/portal-gd/operador", status_code=303)
    except PortalErro:
        return RedirectResponse(
            "/portal-gd/operador?" + urlencode({"aguardando": numero}), status_code=303
        )
    _sincronizar(numero)
    return RedirectResponse("/portal-gd/operador", status_code=303)
