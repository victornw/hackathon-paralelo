from datetime import date, datetime

import pytest

from app.portal_sim.prazos import (
    calcular_prazos,
    dias_uteis_entre,
    eh_dia_util,
    prazos_dos_eventos,
    situacao,
    somar_dias_uteis,
)
from app.schemas import Etapa, EventoPortal, Processo


def ev(etapa: Etapa, d: date) -> EventoPortal:
    return EventoPortal(numero_solicitacao="S-1", etapa=etapa, descricao="", data=d)


def tipos(prazos):
    return [p.tipo for p in prazos]


# --- dias úteis --------------------------------------------------------------


@pytest.mark.parametrize(
    ("d", "util"),
    [
        (date(2026, 11, 13), True),  # sexta
        (date(2026, 11, 14), False),  # sábado
        (date(2026, 11, 15), False),  # domingo (e Proclamação)
        (date(2026, 11, 20), False),  # Consciência Negra, nacional, sexta
        (date(2026, 3, 19), False),  # São José, feriado no Ceará
        (date(2026, 3, 25), False),  # Data Magna do Ceará
        (date(2026, 2, 17), True),  # Carnaval é ponto facultativo
        (date(2026, 12, 25), False),
    ],
)
def test_eh_dia_util(d, util):
    assert eh_dia_util(d) is util


def test_10_dias_uteis_pulando_consciencia_negra():
    # Emitido sex 13/11: 16-19 (4), 20 feriado, 23-27 (9), 30 (10)
    assert somar_dias_uteis(date(2026, 11, 13), 10) == date(2026, 11, 30)


def test_dias_uteis_atravessando_virada_do_ano():
    # 24/12 qui -> 28,29,30,31 (4), 01/01 feriado, 04,05,06,07,08 (9), 11 (10)
    assert somar_dias_uteis(date(2026, 12, 24), 10) == date(2027, 1, 11)


def test_5_dias_uteis_a_partir_de_sabado():
    assert somar_dias_uteis(date(2026, 11, 7), 5) == date(2026, 11, 13)


def test_dias_uteis_entre():
    assert dias_uteis_entre(date(2026, 11, 13), date(2026, 11, 30)) == 10
    assert dias_uteis_entre(date(2026, 11, 30), date(2026, 11, 13)) == -10
    assert dias_uteis_entre(date(2026, 11, 13), date(2026, 11, 13)) == 0


# --- prazos a partir dos eventos ---------------------------------------------


def test_sem_eventos_sem_prazos():
    assert prazos_dos_eventos([]) == []


def test_protocolado_abre_orcamento_15_dias_corridos():
    (p,) = prazos_dos_eventos([ev(Etapa.PROTOCOLADO, date(2026, 11, 9))])
    assert p.tipo == "orcamento"
    assert p.vencimento == date(2026, 11, 24)
    assert p.conta_contra == "distribuidora"
    assert not p.dias_uteis
    assert "art. 64" in p.fonte


def test_orcamento_com_obras_30_dias():
    (p,) = prazos_dos_eventos(
        [ev(Etapa.PROTOCOLADO, date(2026, 11, 9))], com_obras=True
    )
    assert p.dias == 30 and p.vencimento == date(2026, 12, 9)
    assert "com obras" in p.fonte


def test_pendencia_fecha_orcamento_e_abre_30_dias():
    (p,) = prazos_dos_eventos(
        [
            ev(Etapa.PROTOCOLADO, date(2026, 11, 9)),
            ev(Etapa.PENDENCIA, date(2026, 11, 12)),
        ]
    )
    assert p.tipo == "sanar_pendencia"
    assert p.vencimento == date(2026, 12, 12)
    assert p.conta_contra == "integrador"


def test_reenvio_fecha_pendencia_e_reabre_orcamento_na_data_do_reenvio():
    (p,) = prazos_dos_eventos(
        [
            ev(Etapa.PROTOCOLADO, date(2026, 11, 9)),
            ev(Etapa.PENDENCIA, date(2026, 11, 12)),
            ev(Etapa.PROTOCOLADO, date(2026, 11, 14)),
        ]
    )
    assert p.tipo == "orcamento" and p.inicio == date(2026, 11, 14)


def test_orcamento_emitido_abre_10_dias_uteis():
    (p,) = prazos_dos_eventos(
        [
            ev(Etapa.PROTOCOLADO, date(2026, 11, 3)),
            ev(Etapa.ORCAMENTO_EMITIDO, date(2026, 11, 13)),
        ]
    )
    assert p.tipo == "aprovar_orcamento"
    assert p.dias_uteis and p.dias == 10
    assert p.vencimento == date(2026, 11, 30)
    assert "7.3.5" in p.fonte and "art. 83" in p.fonte


def test_aprovacao_abre_contratos_e_vistoria_fecha():
    base = [
        ev(Etapa.PROTOCOLADO, date(2026, 11, 3)),
        ev(Etapa.ORCAMENTO_EMITIDO, date(2026, 11, 13)),
        ev(Etapa.ORCAMENTO_APROVADO, date(2026, 11, 16)),
    ]
    (p,) = prazos_dos_eventos(base)
    assert p.tipo == "devolver_contratos" and p.vencimento == date(2026, 12, 16)

    (v,) = prazos_dos_eventos(
        [*base, ev(Etapa.VISTORIA_SOLICITADA, date(2026, 11, 20))]
    )
    assert v.tipo == "vistoria_ligacao"
    # sex 20/11 é feriado; conta a partir do dia seguinte: 23,24,25,26,27
    assert v.vencimento == date(2026, 11, 27)
    assert v.conta_contra == "distribuidora"


def test_medidor_fecha_tudo():
    eventos = [
        ev(Etapa.PROTOCOLADO, date(2026, 11, 3)),
        ev(Etapa.ORCAMENTO_EMITIDO, date(2026, 11, 13)),
        ev(Etapa.ORCAMENTO_APROVADO, date(2026, 11, 16)),
        ev(Etapa.VISTORIA_SOLICITADA, date(2026, 11, 20)),
        ev(Etapa.MEDIDOR, date(2026, 11, 25)),
    ]
    assert prazos_dos_eventos(eventos) == []


def test_eventos_fora_de_ordem_sao_ordenados_por_data():
    eventos = [
        ev(Etapa.ORCAMENTO_EMITIDO, date(2026, 11, 13)),
        ev(Etapa.PROTOCOLADO, date(2026, 11, 3)),
    ]
    assert tipos(prazos_dos_eventos(eventos)) == ["aprovar_orcamento"]


def test_calcular_prazos_usa_eventos_do_processo():
    proc = Processo(
        id="p",
        criado_em=datetime(2026, 11, 3, 9),
        eventos=[ev(Etapa.PROTOCOLADO, date(2026, 11, 3))],
    )
    assert tipos(calcular_prazos(proc)) == ["orcamento"]


# --- situação ------------------------------------------------------------------


def test_situacao_prazo_uteis():
    (p,) = prazos_dos_eventos(
        [
            ev(Etapa.PROTOCOLADO, date(2026, 11, 3)),
            ev(Etapa.ORCAMENTO_EMITIDO, date(2026, 11, 13)),
        ]
    )  # vence 30/11
    assert situacao(p, date(2026, 11, 16)) == ("no_prazo", 9)
    assert situacao(p, date(2026, 11, 26)) == ("atencao", 2)
    assert situacao(p, date(2026, 11, 30)) == ("vence_hoje", 0)
    assert situacao(p, date(2026, 12, 1)) == ("vencido", -1)


def test_situacao_prazo_corrido():
    (p,) = prazos_dos_eventos([ev(Etapa.PROTOCOLADO, date(2026, 11, 9))])  # vence 24/11
    assert situacao(p, date(2026, 11, 10)) == ("no_prazo", 14)
    assert situacao(p, date(2026, 11, 26)) == ("vencido", -2)
