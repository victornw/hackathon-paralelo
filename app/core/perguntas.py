"""O que falta para fechar o pacote, como tabela de exigências.

Cada exigência diz qual campo precisa, a pergunta objetiva em português, quem
responde e como saber se o dado ainda falta. O id da pergunta é o próprio campo,
então rodar de novo devolve as mesmas perguntas (idempotente). Pergunta já
respondida não volta.

Os campos de formulário do Portal GD que o Processo não tem (telefone,
modalidade...) vêm das respostas: o Portal procura Pergunta.campo igual à chave.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from app.core.arranjo import T_MIN_C, bitola_por_tabela
from app.schemas import CampoExtraido, Pergunta, Processo
from app.tracing import registrar_uso, trace

Destinatario = Literal["integrador", "engenheiro"]


@dataclass(frozen=True)
class Exigencia:
    campo: str
    texto: Callable[[Processo], str]
    destinatario: Destinatario
    falta: Callable[[Processo], bool]


def _fixo(texto: str) -> Callable[[Processo], str]:
    return lambda _: texto


def _numero(valor: float) -> str:
    return f"{valor:g}".replace(".", ",")


def _incerto(campo: CampoExtraido | None) -> bool:
    return campo is None or campo.incerto


def _confirmar_ou_informar(
    campo: CampoExtraido | None, o_que: str, onde: str, unidade: str = ""
) -> str:
    """`o_que` já vem com artigo ("o titular"). Valor lido com pouca confiança
    vira pedido de confirmação; valor ausente vira pedido de informação."""
    if campo is None or campo.valor is None:
        return f"Não consegui ler {o_que} {onde}. Qual é?"
    valor = f"{campo.valor}{unidade}"
    return f'Li {o_que} como "{valor}" {onde}, com confiança baixa. Está correto? Se não, qual é o certo?'


# --- conta de luz ---------------------------------------------------------------------

CAMPOS_DA_CONTA: tuple[tuple[str, str, str], ...] = (
    ("uc", "o código da UC", ""),
    ("titular", "o titular", ""),
    ("cpf_cnpj", "o CPF/CNPJ do titular", ""),
    ("endereco", "o endereço da UC", ""),
    ("cidade", "o município da UC", ""),
    ("classe", "a classe de consumo", ""),
    ("subgrupo", "o subgrupo tarifário", ""),
    ("tipo_ligacao", "o tipo de ligação (monofásico, bifásico ou trifásico)", ""),
    ("tensao_atendimento_v", "a tensão de atendimento", " V"),
)


def _exigencia_da_conta(chave: str, o_que: str, unidade: str) -> Exigencia:
    return Exigencia(
        campo=f"campos.{chave}",
        texto=lambda p: _confirmar_ou_informar(
            p.campos.get(chave), o_que, "na conta de luz", unidade
        ),
        destinatario="integrador",
        falta=lambda p: _incerto(p.campos.get(chave)),
    )


# --- visita, kit e portal ----------------------------------------------------------------


def _texto_bitola(p: Processo) -> str:
    base = "Qual é a bitola do cabo CA entre o inversor e o quadro (mm²)?"
    disjuntor = p.visita.disjuntor_ca_a
    sugerida = None if disjuntor is None else bitola_por_tabela(disjuntor)
    if sugerida is None:
        return base
    return (
        f"{base} Para o disjuntor CA de {_numero(disjuntor)} A, a NBR 5410 (Iz corrigido "
        f"para método B2, 35 °C e 2 circuitos) indica no mínimo {_numero(sugerida)} mm²."
    )


def _texto_disjuntor_padrao(p: Processo) -> str:
    return _confirmar_ou_informar(
        p.visita.disjuntor_padrao_a,
        "o disjuntor geral do padrão de entrada",
        "na foto do padrão",
        " A",
    )


def _texto_confirmar_strings(p: Processo) -> str:
    assert p.kit is not None
    arranjo = "; ".join(
        f"MPPT {s.mppt}: {s.modulos_em_serie} módulos em série"
        for s in sorted(p.kit.strings, key=lambda s: s.mppt)
    )
    return (
        f"Confirma a configuração de strings proposta pelo agente ({arranjo})? "
        f"Ela foi conferida com o Voc corrigido a {_numero(T_MIN_C)} °C."
    )


def _strings_sugeridas(p: Processo) -> bool:
    return p.kit is not None and any(s.sugerida for s in p.kit.strings)


def _sem_resposta(campo: str) -> Callable[[Processo], bool]:
    return lambda p: not any(q.campo == campo and q.resposta for q in p.perguntas)


EXIGENCIAS: tuple[Exigencia, ...] = (
    *(_exigencia_da_conta(*campo) for campo in CAMPOS_DA_CONTA),
    Exigencia(
        "relacao_cargas",
        _fixo(
            "Qual é a relação de cargas da unidade (aparelho, potência em W e quantidade)? "
            "Ela define a carga instalada exigida no Anexo A."
        ),
        "integrador",
        lambda p: not p.visita.relacao_cargas,
    ),
    Exigencia(
        "disjuntor_padrao_a",
        _texto_disjuntor_padrao,
        "integrador",
        lambda p: _incerto(p.visita.disjuntor_padrao_a),
    ),
    Exigencia(
        "bitola_ca_mm2",
        _texto_bitola,
        "integrador",
        lambda p: p.visita.bitola_ca_mm2 is None,
    ),
    Exigencia(
        "distancia_inversor_quadro_m",
        _fixo("Qual é a distância entre o inversor e o quadro de distribuição (m)?"),
        "integrador",
        lambda p: p.visita.distancia_inversor_quadro_m is None,
    ),
    Exigencia(
        "coordenadas_padrao",
        _fixo(
            "Quais são a latitude e a longitude do padrão de entrada (graus decimais)?"
        ),
        "integrador",
        lambda p: p.visita.latitude is None or p.visita.longitude is None,
    ),
    Exigencia(
        "area_concessao",
        _fixo(
            "Em qual área de concessão fica a instalação: Ceará, São Paulo, RJ Serra, "
            "RJ Sul Fluminense ou RJ demais áreas? Ela define a temperatura mínima "
            "usada na tensão das strings no frio."
        ),
        "integrador",
        lambda p: p.visita.area_concessao is None,
    ),
    Exigencia(
        "tipo_ramal",
        _fixo("O ramal de ligação é aéreo ou subterrâneo?"),
        "integrador",
        lambda p: p.visita.tipo_ramal is None,
    ),
    Exigencia(
        "email_contato",
        _fixo(
            "Qual é o e-mail de contato do titular? A consulta no Portal GD usa esse e-mail."
        ),
        "integrador",
        lambda p: not p.email_contato,
    ),
    Exigencia(
        "coef_temp_voc_pct_c",
        lambda p: (
            f"Qual é o coeficiente de temperatura do Voc (%/°C) do módulo {p.kit.modulo.modelo}? "
            "Consta no datasheet."
        ),
        "integrador",
        lambda p: p.kit is not None and p.kit.modulo.coef_temp_voc_pct_c is None,
    ),
    Exigencia(
        "certificado_inmetro",
        lambda p: (
            f"Qual é o número do certificado INMETRO do inversor {p.kit.inversor.modelo}?"
        ),
        "integrador",
        lambda p: (
            p.kit is not None and not (p.kit.inversor.certificado_inmetro or "").strip()
        ),
    ),
    Exigencia(
        "strings",
        _fixo(
            "Quantos módulos em série há em cada MPPT? O agente não conseguiu propor uma "
            "configuração que caiba no inversor."
        ),
        "integrador",
        lambda p: p.kit is not None and not p.kit.strings,
    ),
    Exigencia("strings", _texto_confirmar_strings, "engenheiro", _strings_sugeridas),
    Exigencia(
        "telefone",
        _fixo("Qual é o telefone de contato do titular?"),
        "integrador",
        _sem_resposta("telefone"),
    ),
    Exigencia(
        "qtd_ucs_credito",
        _fixo("Quantas UCs vão receber os créditos de energia?"),
        "integrador",
        _sem_resposta("qtd_ucs_credito"),
    ),
    Exigencia(
        "modalidade_compensacao",
        _fixo(
            "Qual é a modalidade de compensação dos créditos (por exemplo, na própria UC "
            "ou autoconsumo remoto)?"
        ),
        "integrador",
        _sem_resposta("modalidade_compensacao"),
    ),
)


@trace("perguntas_pendentes")
def perguntas_pendentes(processo: Processo) -> list[Pergunta]:
    """Lista o que falta para fechar o pacote. O id é o campo, então chamar de
    novo devolve as mesmas perguntas; as já respondidas ficam de fora."""
    respondidas = {p.campo for p in processo.perguntas if p.resposta is not None}
    pendentes = [
        Pergunta(
            id=e.campo,
            campo=e.campo,
            texto=e.texto(processo),
            destinatario=e.destinatario,
        )
        for e in EXIGENCIAS
        if e.campo not in respondidas and e.falta(processo)
    ]
    registrar_uso(
        decisao=f"{len(pendentes)} pergunta(s) pendente(s) para fechar o pacote."
    )
    return pendentes
