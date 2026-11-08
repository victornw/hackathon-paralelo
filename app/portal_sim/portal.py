"""Portal simulado no formato do Portal GD da Enel. Nunca acessa o portal real.

Formulário básico com os mesmos campos do portal real; consulta por UC, e-mail
e número da solicitação; fluxo roteirizado de status.

Transições (quem age entre parênteses):
  PROTOCOLADO  -> PENDENCIA          (distribuidora; só no 1º envio, se o roteiro tiver pendência)
  PROTOCOLADO  -> ORCAMENTO_EMITIDO  (distribuidora)
  PENDENCIA    -> PROTOCOLADO        (integrador reenvia com a correção)
  ORCAMENTO_EMITIDO   -> ORCAMENTO_APROVADO   (integrador)
  ORCAMENTO_APROVADO  -> VISTORIA_SOLICITADA  (integrador)
  VISTORIA_SOLICITADA -> VISTORIA -> MEDIDOR -> CONCLUIDO (distribuidora)

Campos que o Processo não tem (modalidade, telefone...) vêm das respostas às
perguntas: Pergunta.campo igual à chave do formulário e Pergunta.resposta preenchida.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel

from app.portal_sim.relogio import hoje
from app.schemas import Etapa, EventoPortal, Processo
from app.tracing import registrar_uso, trace
from app.tracing.db import conectar

MOTIVO_PENDENCIA_ROTEIRO = (
    "Diagrama unifilar não apresenta o dispositivo de proteção contra surtos (DPS) "
    "na instalação interna, conforme item 7.6.1.6 da norma CNC-NDBR-DBR-18-0122."
)

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS portal_solicitacoes (
    numero TEXT PRIMARY KEY,
    uc TEXT NOT NULL,
    email TEXT NOT NULL,
    formulario TEXT NOT NULL,
    eventos TEXT NOT NULL,
    com_pendencia INTEGER NOT NULL
);
"""


class PortalErro(Exception):
    """Erro de negócio do portal (mensagem pronta para a tela)."""


class SolicitacaoNaoEncontrada(PortalErro):
    pass


class FormularioBasico(BaseModel):
    """Passo 1 do Portal GD da Enel: formulário básico."""

    codigo_uc: str
    classe: str
    titular: str
    email: str
    endereco: str
    cpf_cnpj: str
    telefone: str
    fonte: str = "Solar fotovoltaica"
    potencia_instalada_geracao_kw: float
    tipo_geracao: str = "Empregando inversor"
    qtd_ucs_credito: int
    data_implantacao: date | None = None
    potencia_instalada_uc_kw: float  # carga instalada
    nivel_tensao: str = "Baixa tensão"
    tipo_conexao: str  # monofásico, bifásico, trifásico
    tensao_atendimento_v: float
    corrente_disjuntor_a: float
    tipo_ramal: str
    subgrupo: str
    modalidade: str
    demanda_kw: float | None = None  # só grupo A
    latitude: float
    longitude: float


def _resposta(processo: Processo, campo: str) -> str | None:
    for p in processo.perguntas:
        if p.campo == campo and p.resposta:
            return p.resposta
    return None


def _valor(processo: Processo, chave: str):
    c = processo.campos.get(chave)
    return None if c is None else c.valor


def montar_formulario(processo: Processo) -> FormularioBasico:
    """Monta o formulário a partir do processo. Falta de dado -> PortalErro com a
    lista do que falta (o agente transforma em pergunta; nada é presumido)."""
    from app.docs.anexo_a import carga_instalada_kw, potencia_instalada_kw

    v = processo.visita
    kit = processo.kit
    dados = {
        "codigo_uc": _valor(processo, "uc"),
        "classe": _valor(processo, "classe"),
        "titular": _valor(processo, "titular"),
        "email": processo.email_contato,
        "endereco": _valor(processo, "endereco"),
        "cpf_cnpj": _valor(processo, "cpf_cnpj"),
        "telefone": _resposta(processo, "telefone"),
        "potencia_instalada_geracao_kw": potencia_instalada_kw(kit) if kit else None,
        "qtd_ucs_credito": _resposta(processo, "qtd_ucs_credito"),
        "potencia_instalada_uc_kw": carga_instalada_kw(processo),
        "tipo_conexao": _valor(processo, "tipo_ligacao"),
        "tensao_atendimento_v": _valor(processo, "tensao_atendimento_v"),
        "corrente_disjuntor_a": v.disjuntor_padrao_a.valor
        if v.disjuntor_padrao_a
        else None,
        "tipo_ramal": v.tipo_ramal,
        "subgrupo": _valor(processo, "subgrupo"),
        "modalidade": _resposta(processo, "modalidade_compensacao"),
        "latitude": v.latitude,
        "longitude": v.longitude,
    }
    faltando = sorted(k for k, val in dados.items() if val is None)
    if faltando:
        raise PortalErro("Campos obrigatórios não preenchidos: " + ", ".join(faltando))
    return FormularioBasico(**dados)


# --- armazenamento --------------------------------------------------------------


def _con():
    con = conectar()
    con.executescript(_ESQUEMA)
    return con


def _carregar(numero: str) -> tuple[dict, list[EventoPortal]]:
    with _con() as con:
        linha = con.execute(
            "SELECT uc, email, eventos, com_pendencia FROM portal_solicitacoes WHERE numero = ?",
            (numero,),
        ).fetchone()
    if linha is None:
        raise SolicitacaoNaoEncontrada("Solicitação não encontrada.")
    uc, email, eventos, com_pendencia = linha
    meta = {"uc": uc, "email": email, "com_pendencia": bool(com_pendencia)}
    return meta, [EventoPortal.model_validate(e) for e in json.loads(eventos)]


def _salvar_eventos(numero: str, eventos: list[EventoPortal]) -> None:
    with _con() as con:
        con.execute(
            "UPDATE portal_solicitacoes SET eventos = ? WHERE numero = ?",
            (json.dumps([e.model_dump(mode="json") for e in eventos]), numero),
        )


def _proximo_numero() -> str:
    ano = hoje().year
    with _con() as con:
        # O maior número + 1, não a contagem: reiniciar a demo apaga solicitações
        # e a contagem repetiria um número que ainda existe.
        (n,) = con.execute(
            "SELECT COALESCE(MAX(CAST(substr(numero, -6) AS INTEGER)), 0)"
            " FROM portal_solicitacoes WHERE numero LIKE ?",
            (f"GD-{ano}-%",),
        ).fetchone()
    return f"GD-{ano}-{n + 1:06d}"


def _evento(numero: str, etapa: Etapa, descricao: str, **extra) -> EventoPortal:
    return EventoPortal(
        numero_solicitacao=numero,
        etapa=etapa,
        descricao=descricao,
        data=hoje(),
        **extra,
    )


# --- ações do integrador ----------------------------------------------------------


@trace("protocolar")
def protocolar(processo: Processo, com_pendencia: bool = True) -> str:
    """Envia o formulário básico ao portal simulado e devolve o número da solicitação.
    Exige a revisão do engenheiro. `com_pendencia` liga a pendência roteirizada."""
    if not processo.revisado_por:
        raise PortalErro("O engenheiro precisa revisar e assinar antes do protocolo.")
    form = montar_formulario(processo)
    numero = _proximo_numero()
    ev = _evento(
        numero, Etapa.PROTOCOLADO, "Solicitação de orçamento de conexão recebida."
    )
    with _con() as con:
        con.execute(
            "INSERT INTO portal_solicitacoes VALUES (?, ?, ?, ?, ?, ?)",
            (
                numero,
                form.codigo_uc,
                form.email.lower(),
                form.model_dump_json(),
                json.dumps([ev.model_dump(mode="json")]),
                int(com_pendencia),
            ),
        )
    registrar_uso(decisao=f"Protocolado no portal simulado: {numero}.")
    return numero


def uc_da_solicitacao(numero_solicitacao: str) -> str:
    """UC de uma solicitação existente; levanta SolicitacaoNaoEncontrada se não há."""
    meta, _ = _carregar(numero_solicitacao.strip())
    return meta["uc"]


def consultar_status(
    uc: str, email: str, numero_solicitacao: str
) -> list[EventoPortal]:
    """Consulta como no Portal GD real: UC, e-mail e número precisam bater."""
    meta, eventos = _carregar(numero_solicitacao.strip())
    if meta["uc"] != uc.strip() or meta["email"] != email.strip().lower():
        raise SolicitacaoNaoEncontrada("Solicitação não encontrada.")
    return eventos


def _etapa_atual(eventos: list[EventoPortal]) -> Etapa:
    return eventos[-1].etapa


def _acao_integrador(
    numero: str, de: Etapa, para: Etapa, descricao: str
) -> EventoPortal:
    _, eventos = _carregar(numero)
    if _etapa_atual(eventos) != de:
        raise PortalErro(
            f"Ação indisponível na etapa atual ({_etapa_atual(eventos).value})."
        )
    ev = _evento(numero, para, descricao)
    _salvar_eventos(numero, [*eventos, ev])
    return ev


def reenviar(numero: str, correcao: str) -> EventoPortal:
    return _acao_integrador(
        numero,
        Etapa.PENDENCIA,
        Etapa.PROTOCOLADO,
        f"Documentação reenviada: {correcao}",
    )


def aprovar_orcamento(numero: str) -> EventoPortal:
    return _acao_integrador(
        numero,
        Etapa.ORCAMENTO_EMITIDO,
        Etapa.ORCAMENTO_APROVADO,
        "Orçamento de conexão aprovado.",
    )


def solicitar_vistoria(numero: str) -> EventoPortal:
    return _acao_integrador(
        numero,
        Etapa.ORCAMENTO_APROVADO,
        Etapa.VISTORIA_SOLICITADA,
        "Vistoria solicitada; instalação concluída.",
    )


# --- lado da distribuidora (roteiro da demo) ------------------------------------

_DISTRIBUIDORA: dict[Etapa, tuple[Etapa, str]] = {
    Etapa.PROTOCOLADO: (Etapa.ORCAMENTO_EMITIDO, "Orçamento de conexão emitido."),
    Etapa.VISTORIA_SOLICITADA: (Etapa.VISTORIA, "Vistoria realizada e aprovada."),
    Etapa.VISTORIA: (Etapa.MEDIDOR, "Medidor bidirecional instalado."),
    Etapa.MEDIDOR: (Etapa.CONCLUIDO, "Conexão concluída; geração liberada."),
}


_VEZ_DO_INTEGRADOR = {
    Etapa.PENDENCIA,
    Etapa.ORCAMENTO_EMITIDO,
    Etapa.ORCAMENTO_APROVADO,
}


def vez_de(etapa: Etapa) -> str | None:
    """Quem precisa agir agora: "distribuidora", "integrador" ou None (concluído)."""
    if etapa in _VEZ_DO_INTEGRADOR:
        return "integrador"
    if etapa == Etapa.PROTOCOLADO or etapa in _DISTRIBUIDORA:
        return "distribuidora"
    return None


def avancar_distribuidora(numero: str) -> EventoPortal:
    """Próximo passo da distribuidora no roteiro. No primeiro protocolo de um
    roteiro com pendência, a distribuidora aponta a pendência roteirizada."""
    meta, eventos = _carregar(numero)
    atual = _etapa_atual(eventos)
    ja_teve_pendencia = any(e.etapa == Etapa.PENDENCIA for e in eventos)
    if atual == Etapa.PROTOCOLADO and meta["com_pendencia"] and not ja_teve_pendencia:
        ev = _evento(
            numero,
            Etapa.PENDENCIA,
            "Documentação com pendência.",
            motivo_pendencia=MOTIVO_PENDENCIA_ROTEIRO,
        )
    elif atual in _DISTRIBUIDORA:
        etapa, descricao = _DISTRIBUIDORA[atual]
        ev = _evento(numero, etapa, descricao)
    else:
        raise PortalErro(f"Aguardando o integrador (etapa {atual.value}).")
    _salvar_eventos(numero, [*eventos, ev])
    return ev


# --- leitura para as telas do portal ---------------------------------------------


@dataclass
class ResumoSolicitacao:
    numero: str
    uc: str
    email: str
    titular: str
    etapa: Etapa
    ultima_data: date


def listar_solicitacoes() -> list[ResumoSolicitacao]:
    """Todas as solicitações, da mais recente para a mais antiga."""
    with _con() as con:
        linhas = con.execute(
            "SELECT numero, uc, email, formulario, eventos FROM portal_solicitacoes"
        ).fetchall()
    resumos = []
    for numero, uc, email, formulario, eventos in linhas:
        evs = [EventoPortal.model_validate(e) for e in json.loads(eventos)]
        resumos.append(
            ResumoSolicitacao(
                numero=numero,
                uc=uc,
                email=email,
                titular=json.loads(formulario).get("titular", ""),
                etapa=_etapa_atual(evs),
                ultima_data=evs[-1].data,
            )
        )
    resumos.sort(key=lambda r: (r.ultima_data, r.numero), reverse=True)
    return resumos


def formulario(numero: str) -> FormularioBasico:
    """Formulário básico enviado na solicitação."""
    with _con() as con:
        linha = con.execute(
            "SELECT formulario FROM portal_solicitacoes WHERE numero = ?",
            (numero.strip(),),
        ).fetchone()
    if linha is None:
        raise SolicitacaoNaoEncontrada("Solicitação não encontrada.")
    return FormularioBasico.model_validate_json(linha[0])
