"""Relógio de prazos: código determinístico a partir dos eventos do portal.

Convenções (testadas em tests/test_prazos.py):
- A contagem começa no dia seguinte ao evento que abre o prazo.
- Dias úteis excluem sábado, domingo e feriados nacionais e do Ceará
  (biblioteca `holidays`, Brasil subdivisão CE). Carnaval é ponto facultativo
  e não entra como feriado.
- Prazos em dias corridos vencem exatamente em início + N dias; não aplicamos
  prorrogação para o próximo dia útil (a norma Enel não diz isso).
- Um prazo some da lista quando o evento que o fecha acontece.

Quem abre e quem fecha cada prazo:
| Prazo              | Abre                 | Fecha                                 |
| orcamento          | PROTOCOLADO          | PENDENCIA ou ORCAMENTO_EMITIDO        |
| sanar_pendencia    | PENDENCIA            | PROTOCOLADO (reenvio) ou ORC_EMITIDO  |
| aprovar_orcamento  | ORCAMENTO_EMITIDO    | ORCAMENTO_APROVADO                    |
| devolver_contratos | ORCAMENTO_APROVADO   | VISTORIA_SOLICITADA (*)               |
| vistoria_ligacao   | VISTORIA_SOLICITADA  | MEDIDOR ou CONCLUIDO                  |

(*) O portal simulado envia os contratos junto com a aprovação do orçamento
e trata o pedido de vistoria como sinal de contratos devolvidos.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import cache
from typing import Literal

import holidays

from app.schemas import Etapa, EventoPortal, Prazo, Processo

TipoPrazo = Literal[
    "orcamento",
    "aprovar_orcamento",
    "devolver_contratos",
    "sanar_pendencia",
    "vistoria_ligacao",
]


@cache
def _feriados(ano: int) -> holidays.HolidayBase:
    return holidays.Brazil(subdiv="CE", years=ano)


def eh_dia_util(d: date) -> bool:
    return d.weekday() < 5 and d not in _feriados(d.year)


def somar_dias_uteis(inicio: date, n: int) -> date:
    d = inicio
    while n > 0:
        d += timedelta(days=1)
        if eh_dia_util(d):
            n -= 1
    return d


def dias_uteis_entre(inicio: date, fim: date) -> int:
    """Dias úteis em (inicio, fim]. Negativo quando fim < inicio."""
    if fim < inicio:
        return -dias_uteis_entre(fim, inicio)
    return sum(
        1
        for i in range(1, (fim - inicio).days + 1)
        if eh_dia_util(inicio + timedelta(i))
    )


_REGRAS: dict[TipoPrazo, dict] = {
    "orcamento": {
        "abre": {Etapa.PROTOCOLADO},
        "fecha": {Etapa.PENDENCIA, Etapa.ORCAMENTO_EMITIDO},
        "dias": 15,
        "dias_uteis": False,
        "conta_contra": "distribuidora",
        "fonte": "Norma Enel, Tabela 9 (15 dias sem obras); REN 1.000, art. 64",
    },
    "sanar_pendencia": {
        "abre": {Etapa.PENDENCIA},
        "fecha": {Etapa.PROTOCOLADO, Etapa.ORCAMENTO_EMITIDO},
        "dias": 30,
        "dias_uteis": False,
        "conta_contra": "integrador",
        "fonte": "Lei 14.300 (artigo a confirmar)",
    },
    "aprovar_orcamento": {
        "abre": {Etapa.ORCAMENTO_EMITIDO},
        "fecha": {Etapa.ORCAMENTO_APROVADO},
        "dias": 10,
        "dias_uteis": True,
        "conta_contra": "integrador",
        "fonte": "Norma Enel 7.3.5; REN 1.000, art. 83",
    },
    "devolver_contratos": {
        "abre": {Etapa.ORCAMENTO_APROVADO},
        "fecha": {Etapa.VISTORIA_SOLICITADA},
        "dias": 30,
        "dias_uteis": False,
        "conta_contra": "integrador",
        "fonte": "Norma Enel 7.3.6.4; REN 1.000, art. 83, § 7º, III",
    },
    "vistoria_ligacao": {
        "abre": {Etapa.VISTORIA_SOLICITADA},
        "fecha": {Etapa.MEDIDOR, Etapa.CONCLUIDO},
        "dias": 5,
        "dias_uteis": True,
        "conta_contra": "distribuidora",
        "fonte": "Norma Enel, Tabela 8; REN 1.000 (a norma cita art. 64)",
    },
}


def _montar(tipo: TipoPrazo, inicio: date, com_obras: bool) -> Prazo:
    r = _REGRAS[tipo]
    dias = 30 if (tipo == "orcamento" and com_obras) else r["dias"]
    fonte = r["fonte"]
    if tipo == "orcamento" and com_obras:
        fonte = "Norma Enel, Tabela 9 (30 dias com obras); REN 1.000, art. 64"
    vencimento = (
        somar_dias_uteis(inicio, dias)
        if r["dias_uteis"]
        else inicio + timedelta(days=dias)
    )
    return Prazo(
        tipo=tipo,
        inicio=inicio,
        dias=dias,
        dias_uteis=r["dias_uteis"],
        vencimento=vencimento,
        conta_contra=r["conta_contra"],
        fonte=fonte,
    )


def prazos_dos_eventos(
    eventos: list[EventoPortal], com_obras: bool = False
) -> list[Prazo]:
    abertos: dict[TipoPrazo, date] = {}
    for ev in sorted(
        eventos, key=lambda e: e.data
    ):  # sort estável: mantém a ordem do mesmo dia
        for tipo, r in _REGRAS.items():
            if ev.etapa in r["fecha"]:
                abertos.pop(tipo, None)
        for tipo, r in _REGRAS.items():
            if ev.etapa in r["abre"]:
                abertos[tipo] = ev.data
    return sorted(
        (_montar(t, inicio, com_obras) for t, inicio in abertos.items()),
        key=lambda p: p.vencimento,
    )


def calcular_prazos(processo: Processo, com_obras: bool = False) -> list[Prazo]:
    """Prazos correndo a partir dos eventos do processo (ver tabela no topo)."""
    return prazos_dos_eventos(processo.eventos, com_obras=com_obras)


Situacao = Literal["no_prazo", "atencao", "vence_hoje", "vencido"]


def situacao(prazo: Prazo, hoje: date) -> tuple[Situacao, int]:
    """(situação, dias restantes). Dias restantes na mesma unidade do prazo
    (úteis ou corridos). 'atencao' quando faltam 2 ou menos."""
    if prazo.dias_uteis:
        restantes = dias_uteis_entre(hoje, prazo.vencimento)
    else:
        restantes = (prazo.vencimento - hoje).days
    if hoje > prazo.vencimento:
        return "vencido", restantes
    if hoje == prazo.vencimento:
        return "vence_hoje", 0
    if restantes <= 2:
        return "atencao", restantes
    return "no_prazo", restantes
