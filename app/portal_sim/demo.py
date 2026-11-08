"""Casos prontos da demonstração e o botão "Reiniciar demonstração".

reiniciar_demo() deixa o site num estado conhecido para jurados e ensaio:
- relógio simulado na data da demo (DEMO_DATA no .env; padrão 2026-11-16);
- quatro processos sintéticos, um por momento da história:
    demo-01  em revisão do engenheiro (documentos gerados e conferidos)
    demo-02  protocolado e com pendência aberta no portal
    demo-03  protocolado, orçamento emitido (prazo de 10 dias úteis correndo)
    demo-04  caminho completo até concluído
- as solicitações correspondentes no portal simulado, com datas coerentes.

Tudo passa pelas funções reais (gerar_documentos, regras do conferidor, portal),
nada é escrito à mão no estado. Só os processos demo-* e as solicitações deles
são apagados e recriados; processos criados por quem testa o site ficam.
Usa o repositório do Dev A (salvar, memoria, esquecer) sem alterá-lo.
"""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from pathlib import Path

from app.portal_sim import portal
from app.portal_sim.prazos import calcular_prazos
from app.portal_sim.relogio import definir_data, hoje
from app.schemas import (
    CampoExtraido,
    Carga,
    Etapa,
    Fonte,
    Inversor,
    Pergunta,
    Processo,
    StatusRegra,
)
from app.tracing.db import conectar
from app.tracing.trace import processo_atual

RAIZ = Path(__file__).resolve().parents[2]

# Inversor real dos casos prontos. Fonte: datasheet Sungrow SG4.0/5.0/6.0RS-L,
# versão 14 (2025), coluna SG5.0RS-L. Registro INMETRO 005485/2023 (ativo; a
# descrição atual não cita a tensão, então a R05 pede a confirmação do engenheiro).
# Bornes CA: conector plug and play, máx. 6 mm². O módulo segue sintético.
INVERSOR_DEMO = Inversor(
    fabricante="SUNGROW",
    modelo="SG5.0RS-L",
    potencia_nominal_w=5000,
    potencia_max_cc_w=7500,  # potência FV máxima recomendada: 7,5 kWp
    tensao_max_cc_v=600,
    mppt_min_v=40,
    mppt_max_v=560,
    num_mppt=2,
    corrente_max_entrada_a=16,  # por MPPT (32 A no total)
    corrente_max_saida_a=22.8,
    tensao_saida_v=220,
    certificado_inmetro="005485/2023",
    terminal_ca_max_mm2=6,
)
DATA_PADRAO = date(2026, 11, 16)
ENGENHEIRO = "Eng. Demonstração (CREA sintético)"
EMAIL = "integrador.demo@exemplo.com"

# id, titular, UC
CASOS = [
    ("demo-01", "ANA SINTETICA MOREIRA", "7100000001"),
    ("demo-02", "BRUNO FICTICIO SANTOS", "7100000002"),
    ("demo-03", "CARLA EXEMPLO NUNES", "7100000003"),
    ("demo-04", "DANIEL MODELO RAMOS", "7100000004"),
]


def data_demo() -> date:
    valor = os.environ.get("DEMO_DATA")
    return date.fromisoformat(valor) if valor else DATA_PADRAO


def _campo(valor: str, documento: str = "conta_luz.pdf") -> CampoExtraido:
    return CampoExtraido(valor=valor, confianca=0.97, fonte=Fonte(documento=documento))


def _respondida(campo: str, texto: str, resposta: str, quando: date) -> Pergunta:
    return Pergunta(
        id=f"demo:{campo}",
        campo=campo,
        texto=texto,
        resposta=resposta,
        respondida_em=datetime.combine(quando, time(10, 0)),
    )


def _base(pid: str, titular: str, uc: str, inicio: date) -> Processo:
    """Processo pronto para revisão: dados da conta, kit e visita completos."""
    exemplo = Processo.model_validate_json(
        (RAIZ / "fixtures" / "processo_exemplo.json").read_text()
    )
    p = exemplo.model_copy(deep=True)
    p.id = pid
    p.criado_em = datetime.combine(inicio, time(9, 0))
    p.etapa = Etapa.MONTAGEM
    p.email_contato = EMAIL
    p.campos["titular"] = _campo(titular)
    p.campos["uc"] = _campo(uc)
    p.campos["consumo_medio_kwh"] = _campo("620")
    p.kit.inversor = INVERSOR_DEMO.model_copy(deep=True)
    p.visita.bitola_ca_mm2 = 6
    p.visita.area_concessao = "ceara"
    p.visita.relacao_cargas = [
        Carga(descricao="Geladeira", potencia_w=250),
        Carga(descricao="Ar-condicionado 12.000 BTU", potencia_w=1100),
        Carga(descricao="Chuveiro elétrico", potencia_w=5500),
        Carga(descricao="Iluminação e tomadas", potencia_w=800),
    ]
    p.regras = []
    p.documentos = []
    p.eventos = []
    p.prazos = []
    # Dados do formulário do Portal GD que não vêm da conta nem do kit
    p.perguntas = [
        _respondida(
            "telefone",
            "O formulário do Portal GD pede um telefone de contato do titular. Qual é?",
            "(00) 90000-0000",
            inicio,
        ),
        _respondida(
            "modalidade_compensacao",
            "Como os créditos de energia serão usados? O Portal GD pede a modalidade de compensação (por exemplo, autoconsumo local, só nesta casa).",
            "Autoconsumo local",
            inicio,
        ),
        _respondida(
            "dps_especificacao",
            "Qual é a especificação do DPS CA da instalação interna (classe, Uc e In)?",
            "classe II, 275 V, 20 kA",
            inicio,
        ),
        _respondida(
            "qtd_ucs_credito",
            "Quantas unidades consumidoras vão receber os créditos? Se for só esta casa, a resposta é 1.",
            "1",
            inicio,
        ),
    ]
    return p


def _confirmar_strings(p: Processo) -> None:
    for s in p.kit.strings:
        s.sugerida = False


def _preparar_para_revisao(p: Processo) -> Processo:
    """Gera documentos e confere as regras com as funções reais."""
    from app.core.regras import conferir
    from app.docs.gerar import gerar_documentos

    p.documentos = gerar_documentos(p)
    p.regras = conferir(p)
    reprovadas = [r.regra_id for r in p.regras if r.status == StatusRegra.REPROVADA]
    if reprovadas:
        raise RuntimeError(f"Caso de demo {p.id} reprovado em {reprovadas}.")
    p.etapa = Etapa.EM_REVISAO
    return p


def _revisar(p: Processo, quando: date) -> None:
    """O engenheiro revisou e assinou: confirma também a R05, se ela pedir."""
    from app.core.parecer import r05_inmetro

    if any(r.regra_id == "R05" and r.valores.get("confirmavel") for r in p.regras):
        r05_inmetro.confirmar(p, ENGENHEIRO)
    p.revisado_por = ENGENHEIRO
    p.revisado_em = datetime.combine(quando, time(11, 0))


def _sincronizar_portal(p: Processo) -> None:
    p.eventos = portal.consultar_status(
        p.campos["uc"].valor, p.email_contato, p.numero_solicitacao
    )
    p.etapa = p.eventos[-1].etapa
    p.prazos = calcular_prazos(p)


def _limpar() -> None:
    from app.core import repositorio as repo

    ids = [pid for pid, _, _ in CASOS]
    ucs = [uc for _, _, uc in CASOS]
    marcas = ",".join("?" * len(ids))
    with portal._con() as con:
        con.execute(f"DELETE FROM portal_solicitacoes WHERE uc IN ({marcas})", ucs)
    with conectar() as con:
        con.execute(f"DELETE FROM passos_trace WHERE processo_id IN ({marcas})", ids)
    for pid in ids:
        for passo in repo.memoria(pid):
            repo.esquecer(pid, passo)


def reiniciar_demo() -> date:
    """Recria os casos de demonstração e põe o relógio na data da demo."""
    from app.core import repositorio as repo

    d = data_demo()
    _limpar()
    casos = {pid: (titular, uc) for pid, titular, uc in CASOS}

    # demo-04: caminho completo, sem pendência
    definir_data(d - timedelta(days=45))
    p4 = _base("demo-04", *casos["demo-04"], hoje())
    with processo_atual(p4.id):
        _confirmar_strings(p4)
        _preparar_para_revisao(p4)
        _revisar(p4, hoje())
        p4.numero_solicitacao = portal.protocolar(p4, com_pendencia=False)
    definir_data(d - timedelta(days=35))
    portal.avancar_distribuidora(p4.numero_solicitacao)  # orçamento emitido
    definir_data(d - timedelta(days=32))
    portal.aprovar_orcamento(p4.numero_solicitacao)
    definir_data(d - timedelta(days=18))
    portal.solicitar_vistoria(p4.numero_solicitacao)
    definir_data(d - timedelta(days=15))
    portal.avancar_distribuidora(p4.numero_solicitacao)  # vistoria
    definir_data(d - timedelta(days=13))
    portal.avancar_distribuidora(p4.numero_solicitacao)  # medidor
    portal.avancar_distribuidora(p4.numero_solicitacao)  # concluído
    _sincronizar_portal(p4)
    repo.salvar(p4)

    # demo-03: orçamento emitido há 4 dias, prazo de aprovação correndo
    definir_data(d - timedelta(days=14))
    p3 = _base("demo-03", *casos["demo-03"], hoje())
    with processo_atual(p3.id):
        _confirmar_strings(p3)
        _preparar_para_revisao(p3)
        _revisar(p3, hoje())
        p3.numero_solicitacao = portal.protocolar(p3, com_pendencia=False)
    definir_data(d - timedelta(days=4))
    portal.avancar_distribuidora(p3.numero_solicitacao)  # orçamento emitido
    _sincronizar_portal(p3)
    repo.salvar(p3)

    # demo-02: protocolado há 6 dias, pendência aberta há 3
    definir_data(d - timedelta(days=8))
    p2 = _base("demo-02", *casos["demo-02"], hoje())
    with processo_atual(p2.id):
        _confirmar_strings(p2)
        _preparar_para_revisao(p2)
        definir_data(d - timedelta(days=6))
        _revisar(p2, hoje())
        p2.numero_solicitacao = portal.protocolar(p2, com_pendencia=True)
    definir_data(d - timedelta(days=3))
    portal.avancar_distribuidora(p2.numero_solicitacao)  # pendência roteirizada
    _sincronizar_portal(p2)
    repo.salvar(p2)

    # demo-01: chegou hoje à revisão; strings ainda sugeridas para o engenheiro
    definir_data(d - timedelta(days=1))
    p1 = _base("demo-01", *casos["demo-01"], hoje())
    with processo_atual(p1.id):
        _preparar_para_revisao(p1)
    p1.perguntas.append(
        Pergunta(
            id="demo:strings",
            campo="strings",
            texto="Confirma 2 strings de 5 módulos, uma em cada MPPT?",
            destinatario="engenheiro",
        )
    )
    repo.salvar(p1)

    return definir_data(d)


def garantir_demo() -> bool:
    """Ao subir o site: se os casos prontos não existem (banco novo, como no plano
    grátis do Render, que apaga o disco a cada deploy ou reinício), recria-os.
    Devolve True quando recriou. Desligável com DEMO_AUTO=0."""
    if os.environ.get("DEMO_AUTO") == "0":
        return False
    from app.core import repositorio as repo

    existentes = {p.id for p in repo.listar()}
    if all(pid in existentes for pid, _, _ in CASOS):
        return False
    reiniciar_demo()
    return True
