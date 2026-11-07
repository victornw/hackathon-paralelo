"""Repositório de regras do conferidor (R01 a R08) e o motor que aplica a política
de quatro estados.

Cada regra declara as entradas nomeadas de que precisa e uma função pura que
devolve APROVADA, REPROVADA ou INCERTA. Quem decide o que acontece com dado
ausente, valor sugerido pelo agente ou erro interno é o motor, não a regra:

1. regra sem função (fora do MVP) -> NAO_VERIFICADA;
2. entrada ausente -> INCERTA, e a função nem roda;
3. entrada sugerida e veredito APROVADA -> INCERTA;
4. função que levanta exceção -> INCERTA, nunca APROVADA;
5. critério marcado a_validar -> INCERTA mesmo com cálculo favorável.

NAO_VERIFICADA não é expressável por uma função de regra.
"""

from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pypdf

from app.core.arranjo import CABO_IZ_A, T_MIN_C, voc_corrigido_v
from app.schemas import (
    Camada,
    DocumentoGerado,
    Processo,
    ResultadoRegra,
    StatusRegra,
    StringFV,
)
from app.tracing import registrar_uso, trace

POTENCIA_MAX_INMETRO_W = 75_000

Entrada = tuple[Any, bool]  # (valor ou None, sugerido pelo agente)

# ---------------------------------------------------------------------------
# Veredito
# ---------------------------------------------------------------------------


_STATUS_DE_REGRA = (StatusRegra.APROVADA, StatusRegra.REPROVADA, StatusRegra.INCERTA)


@dataclass(frozen=True)
class Veredito:
    status: StatusRegra
    mensagem: str
    valores: dict[str, float | str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in _STATUS_DE_REGRA:
            raise ValueError(f"Uma regra não pode devolver {self.status.value}.")


def aprovada(mensagem: str, **valores: float | str) -> Veredito:
    return Veredito(StatusRegra.APROVADA, mensagem, valores)


def reprovada(mensagem: str, **valores: float | str) -> Veredito:
    return Veredito(StatusRegra.REPROVADA, mensagem, valores)


def incerta(mensagem: str, **valores: float | str) -> Veredito:
    return Veredito(StatusRegra.INCERTA, mensagem, valores)


def br(valor: float, casas: int = 1) -> str:
    """Número no formato brasileiro; inteiro sai sem decimais."""
    if float(valor).is_integer():
        return f"{int(valor):,}".replace(",", ".")
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------
# Entradas nomeadas
# ---------------------------------------------------------------------------

ENTRADAS: dict[str, Callable[[Processo], Entrada]] = {}
ROTULOS: dict[str, str] = {}


def _entrada(nome: str, rotulo: str):
    def registrar(resolver: Callable[[Processo], Entrada]):
        ENTRADAS[nome] = resolver
        ROTULOS[nome] = rotulo
        return resolver

    return registrar


def _do_kit(nome: str, rotulo: str, extrair: Callable[[Any], Any]) -> None:
    def resolver(p: Processo) -> Entrada:
        return (None, False) if p.kit is None else (extrair(p.kit), False)

    _entrada(nome, rotulo)(resolver)


def _da_conta(nome: str, rotulo: str, chave: str) -> None:
    def resolver(p: Processo) -> Entrada:
        campo = p.campos.get(chave)
        valor = None if campo is None else campo.valor
        if isinstance(valor, str) and not valor.strip():
            valor = None
        return valor, False

    _entrada(nome, rotulo)(resolver)


_do_kit(
    "corrente_saida_a",
    "corrente máxima de saída do inversor",
    lambda k: k.inversor.corrente_max_saida_a,
)
_do_kit("voc_v", "Voc do módulo", lambda k: k.modulo.voc_v)
_do_kit(
    "coef_temp_voc_pct_c",
    "coeficiente de temperatura do Voc do módulo",
    lambda k: k.modulo.coef_temp_voc_pct_c,
)
_do_kit(
    "tensao_max_cc_v",
    "tensão máxima CC do inversor",
    lambda k: k.inversor.tensao_max_cc_v,
)
_do_kit(
    "potencia_modulos_w", "potência total dos módulos", lambda k: k.potencia_total_wp
)
_do_kit(
    "potencia_max_cc_w",
    "potência máxima CC do inversor",
    lambda k: k.inversor.potencia_max_cc_w,
)
_do_kit(
    "potencia_nominal_w",
    "potência nominal do inversor",
    lambda k: k.inversor.potencia_nominal_w,
)
_do_kit("modelo_inversor", "modelo do inversor", lambda k: k.inversor.modelo)
_do_kit("modelo_modulo", "modelo do módulo", lambda k: k.modulo.modelo)
_do_kit("qtd_modulos", "quantidade de módulos", lambda k: k.qtd_modulos)
_do_kit(
    "certificado_inmetro",
    "certificado INMETRO do inversor",
    lambda k: (k.inversor.certificado_inmetro or "").strip() or None,
)
_da_conta("titular", "titular da UC", "titular")
_da_conta("uc", "código da UC", "uc")


@_entrada("disjuntor_ca_a", "disjuntor CA")
def _disjuntor_ca(p: Processo) -> Entrada:
    return p.visita.disjuntor_ca_a, False


@_entrada("bitola_ca_mm2", "bitola do cabo CA")
def _bitola(p: Processo) -> Entrada:
    return p.visita.bitola_ca_mm2, False


@_entrada("strings", "configuração de strings")
def _strings(p: Processo) -> Entrada:
    if p.kit is None or not p.kit.strings:
        return None, False
    strings = tuple(sorted(p.kit.strings, key=lambda s: s.mppt))
    return strings, any(s.sugerida for s in strings)


@_entrada("documentos", "documentos gerados")
def _documentos(p: Processo) -> Entrada:
    return (tuple(p.documentos) or None), False


def _texto_entrada(valor: Any) -> float | str:
    if isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, (int, float, str)):
        return valor
    if isinstance(valor, StringFV):
        return f"MPPT {valor.mppt}: {valor.modulos_em_serie} módulos"
    if isinstance(valor, DocumentoGerado):
        return valor.nome_arquivo
    if isinstance(valor, (tuple, list)):
        return "; ".join(str(_texto_entrada(v)) for v in valor)
    return str(valor)


# ---------------------------------------------------------------------------
# Regras
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Regra:
    id: str
    descricao: str
    camada: Camada
    fonte_norma: str
    a_validar: bool
    entradas: tuple[str, ...]
    avaliar: Callable[[dict[str, Any]], Veredito] | None
    fora_do_mvp: str = ""


# --- R01: coerência entre documentos -----------------------------------------

_NOME_DOCUMENTO = {
    "solicitacao_orcamento": "Solicitação (Anexo A)",
    "memorial": "Memorial descritivo",
    "unifilar": "Unifilar",
}

_ITENS_COMUNS = ("titular", "uc", "modelo_inversor", "modelo_modulo", "qtd_modulos")
# O Anexo A só imprime o disjuntor do padrão, não o disjuntor CA.
_ITENS_POR_DOCUMENTO: dict[str, tuple[str, ...]] = {
    "solicitacao_orcamento": _ITENS_COMUNS,
    "memorial": (*_ITENS_COMUNS, "disjuntor_ca_a"),
    "unifilar": (*_ITENS_COMUNS, "disjuntor_ca_a"),
}


def _normalizar(texto: str) -> str:
    """Sem acento, minúsculo e sem espaço: a quebra de linha do PDF pode cair
    em qualquer ponto de um nome composto."""
    sem_acento = unicodedata.normalize("NFKD", texto.replace("×", "x"))
    sem_acento = sem_acento.encode("ascii", "ignore").decode()
    return re.sub(r"\s+", "", sem_acento).casefold()


def _texto_valor(valor: Any) -> str:
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def _numero_impresso(valor: float) -> str:
    return f"{valor:g}".replace(".", ",")


# O memorial imprime "Disjuntor CA do inversor 25 A" e o unifilar "DISJUNTOR CA 25 A".
# Ancorar no rótulo evita casar o disjuntor do padrão, que também tem "A".
_PADROES: dict[str, Callable[[Any], str]] = {
    "titular": lambda v: re.escape(_normalizar(_texto_valor(v))),
    "uc": lambda v: rf"(?<!\d){re.escape(_normalizar(_texto_valor(v)))}(?!\d)",
    "modelo_inversor": lambda v: re.escape(_normalizar(_texto_valor(v))),
    "modelo_modulo": lambda v: re.escape(_normalizar(_texto_valor(v))),
    "qtd_modulos": lambda v: rf"(?<!\d){int(v)}x",
    "disjuntor_ca_a": lambda v: (
        rf"disjuntorca(?:doinversor)?{_numero_impresso(float(v))}a(?![\d,])"
    ),
}


def _texto_do_documento(doc: DocumentoGerado) -> str | None:
    try:
        if doc.formato == "pdf":
            leitor = pypdf.PdfReader(doc.caminho)
            texto = "\n".join(pagina.extract_text() or "" for pagina in leitor.pages)
        else:
            marcado = Path(doc.caminho).read_text(encoding="utf-8")
            texto = html.unescape(re.sub(r"<[^>]+>", " ", marcado))
    except Exception:  # noqa: BLE001 - arquivo ilegível vira INCERTA, não erro
        return None
    return texto if texto.strip() else None


def _texto_do_tipo(documentos: tuple[DocumentoGerado, ...], tipo: str) -> str | None:
    candidatos = sorted(
        (d for d in documentos if d.tipo == tipo), key=lambda d: d.formato != "pdf"
    )
    for doc in candidatos:
        texto = _texto_do_documento(doc)
        if texto is not None:
            return texto
    return None


def _coerencia(v: dict[str, Any]) -> Veredito:
    documentos: tuple[DocumentoGerado, ...] = v["documentos"]
    divergencias: list[str] = []
    ilegiveis: list[str] = []
    for tipo, itens in _ITENS_POR_DOCUMENTO.items():
        nome = _NOME_DOCUMENTO[tipo]
        texto = _texto_do_tipo(documentos, tipo)
        if texto is None:
            ilegiveis.append(nome)
            continue
        normalizado = _normalizar(texto)
        for item in itens:
            if not re.search(_PADROES[item](v[item]), normalizado):
                divergencias.append(
                    f"{nome}: não traz {ROTULOS[item]} ({_texto_valor(v[item])})"
                )
    if divergencias:
        return reprovada(
            "Documentos divergem do processo. " + "; ".join(divergencias) + "."
        )
    if ilegiveis:
        return incerta(
            "Documento ausente ou ilegível, coerência não conferida: "
            + ", ".join(ilegiveis)
            + "."
        )
    return aprovada(
        "Titular, UC, modelos, quantidade de módulos e disjuntor CA coerentes "
        "entre solicitação, memorial e unifilar."
    )


# --- R02: disjuntor CA ----------------------------------------------------------


def _disjuntor_entre_corrente_e_cabo(v: dict[str, Any]) -> Veredito:
    ib, i_n, bitola = v["corrente_saida_a"], v["disjuntor_ca_a"], v["bitola_ca_mm2"]
    iz = CABO_IZ_A.get(bitola)
    if iz is None:
        return incerta(
            f"Bitola de {br(bitola)} mm² fora da tabela de capacidade de condução "
            "(NBR 5410, Tabela 36); a capacidade do cabo não foi conferida."
        )
    falhas = []
    if not ib < i_n:
        falhas.append(
            f"corrente máxima de saída ({br(ib)} A) não é menor que o disjuntor de {br(i_n)} A"
        )
    if not i_n < iz:
        falhas.append(
            f"disjuntor de {br(i_n)} A não é menor que a capacidade do cabo de "
            f"{br(bitola)} mm² ({br(iz)} A)"
        )
    if falhas:
        return reprovada(
            "Disjuntor CA fora da faixa: " + "; ".join(falhas) + ".",
            capacidade_cabo_a=iz,
        )
    return aprovada(
        f"{br(ib)} A < disjuntor de {br(i_n)} A < {br(iz)} A do cabo de {br(bitola)} mm² "
        "(tabela de capacidade a validar com engenheiro).",
        capacidade_cabo_a=iz,
    )


# --- R03: tensão das strings -------------------------------------------------------


def _tensao_das_strings(v: dict[str, Any]) -> Veredito:
    strings: tuple[StringFV, ...] = v["strings"]
    limite = v["tensao_max_cc_v"]
    voc_frio = voc_corrigido_v(v["voc_v"], v["coef_temp_voc_pct_c"])
    tensoes = [(s, round(s.modulos_em_serie * voc_frio, 6)) for s in strings]
    pior, tensao = max(tensoes, key=lambda t: t[1])
    valores = {
        "modulos_em_serie": pior.modulos_em_serie,
        "voc_corrigido_v": round(voc_frio, 2),
        "tensao_string_v": round(tensao, 2),
        "temperatura_minima_c": T_MIN_C,
    }
    nota = (
        f"Voc corrigido a {br(T_MIN_C)} °C; coeficiente de temperatura fixo, "
        "a validar com engenheiro."
    )
    acima = [(s, t) for s, t in tensoes if t > limite]
    if acima:
        detalhe = "; ".join(
            f"MPPT {s.mppt} ({s.modulos_em_serie} módulos): {br(t)} V" for s, t in acima
        )
        return reprovada(
            f"Tensão da string acima do máximo CC de {br(limite)} V: {detalhe}. {nota}",
            **valores,
        )
    return aprovada(
        f"String de {pior.modulos_em_serie} módulos: {br(tensao)} V ≤ {br(limite)} V. {nota}",
        **valores,
    )


# --- R04: potência CC ----------------------------------------------------------------


def _potencia_cc(v: dict[str, Any]) -> Veredito:
    modulos, limite = round(v["potencia_modulos_w"], 6), v["potencia_max_cc_w"]
    if modulos <= limite:
        return aprovada(f"{br(modulos)} W de módulos ≤ {br(limite)} W de entrada CC.")
    return reprovada(
        f"{br(modulos)} W de módulos acima dos {br(limite)} W de entrada CC."
    )


# --- R05: certificado INMETRO ----------------------------------------------------------


def _inmetro(v: dict[str, Any]) -> Veredito:
    potencia = v["potencia_nominal_w"]
    if potencia > POTENCIA_MAX_INMETRO_W:
        return incerta(
            f"Inversor de {br(potencia)} W acima de 75 kW: fora do critério de "
            "inversor com certificado INMETRO das Tabelas 10 e 11."
        )
    return incerta(
        f"Certificado INMETRO informado ({v['certificado_inmetro']}). Só a presença foi "
        "conferida; o número não foi checado no registro do INMETRO, nem a correspondência "
        "com modelo e tensão. Anexe e valide a comprovação antes de aprovar."
    )


REGRAS: tuple[Regra, ...] = (
    Regra(
        "R01",
        "Coerência: o mesmo dado é igual em solicitação, memorial e unifilar",
        Camada.TECNICA,
        "Prática; erros recorrentes",
        False,
        (
            "titular",
            "uc",
            "modelo_inversor",
            "modelo_modulo",
            "qtd_modulos",
            "disjuntor_ca_a",
            "documentos",
        ),
        _coerencia,
    ),
    Regra(
        "R02",
        "Disjuntor CA entre corrente de projeto e capacidade do cabo",
        Camada.TECNICA,
        "NBR 5410",
        True,
        ("corrente_saida_a", "disjuntor_ca_a", "bitola_ca_mm2"),
        _disjuntor_entre_corrente_e_cabo,
    ),
    Regra(
        "R03",
        "Módulos por string × Voc corrigido ≤ tensão máxima CC",
        Camada.TECNICA,
        "Datasheets",
        True,
        ("strings", "voc_v", "coef_temp_voc_pct_c", "tensao_max_cc_v"),
        _tensao_das_strings,
    ),
    Regra(
        "R04",
        "Potência dos módulos ≤ potência máxima CC do inversor",
        Camada.TECNICA,
        "Datasheets",
        False,
        ("potencia_modulos_w", "potencia_max_cc_w"),
        _potencia_cc,
    ),
    Regra(
        "R05",
        "Inversor até 75 kW com certificado INMETRO",
        Camada.DISTRIBUIDORA,
        "Norma Enel v05, Tabelas 10 e 11 e 7.6.1.4; Portarias INMETRO 140/2022 e 515/2023",
        False,
        ("potencia_nominal_w", "certificado_inmetro"),
        _inmetro,
    ),
    Regra(
        "R06",
        "Coordenada do padrão de entrada coerente com o endereço cadastrado",
        Camada.DISTRIBUIDORA,
        "Cartilha Cemig 2025",
        False,
        (),
        None,
        "Fora do MVP: exige geocodificação e a fonte é da Cemig.",
    ),
    Regra(
        "R07",
        "Tensão e tipo de ligação coerentes com a potência disponibilizada",
        Camada.DISTRIBUIDORA,
        "Norma Enel, Tabela 4",
        False,
        (),
        None,
        "Fora do MVP: planejada para a fase 2.",
    ),
    Regra(
        "R08",
        "Ajustes de proteção do inversor conforme a tabela da distribuidora",
        Camada.DISTRIBUIDORA,
        "Norma Enel, Anexo G",
        False,
        (),
        None,
        "Fora do MVP: os valores do Anexo G ainda estão 'a informar' para o Ceará.",
    ),
)

_POR_ID = {r.id: r for r in REGRAS}


def _validar_registro() -> None:
    for regra in REGRAS:
        desconhecidas = [n for n in regra.entradas if n not in ENTRADAS]
        if desconhecidas:
            raise ValueError(f"{regra.id} usa entradas sem resolvedor: {desconhecidas}")
    for item in {i for itens in _ITENS_POR_DOCUMENTO.values() for i in itens}:
        if item not in _PADROES or item not in ENTRADAS:
            raise ValueError(f"R01 sem padrão ou entrada para {item}")
    if len(_POR_ID) != len(REGRAS):
        raise ValueError("Ids de regra duplicados.")


_validar_registro()


# ---------------------------------------------------------------------------
# Motor
# ---------------------------------------------------------------------------


def _resultado(
    regra: Regra, veredito: Veredito, usados: dict[str, float | str]
) -> ResultadoRegra:
    if regra.a_validar and veredito.status == StatusRegra.APROVADA:
        veredito = incerta(
            "Cálculo favorável, mas o critério técnico ainda precisa de validação. "
            + veredito.mensagem,
            **veredito.valores,
        )
    return ResultadoRegra(
        regra_id=regra.id,
        descricao=regra.descricao,
        camada=regra.camada,
        status=veredito.status,
        valores={**usados, **veredito.valores},
        mensagem=veredito.mensagem,
        fonte_norma=regra.fonte_norma,
        a_validar=regra.a_validar,
    )


def _aplicar(regra: Regra, processo: Processo) -> ResultadoRegra:
    if regra.avaliar is None:
        return ResultadoRegra(
            regra_id=regra.id,
            descricao=regra.descricao,
            camada=regra.camada,
            status=StatusRegra.NAO_VERIFICADA,
            mensagem=regra.fora_do_mvp,
            fonte_norma=regra.fonte_norma,
            a_validar=regra.a_validar,
        )

    resolvidas = {nome: ENTRADAS[nome](processo) for nome in regra.entradas}
    valores = {nome: valor for nome, (valor, _) in resolvidas.items()}
    usados = {
        nome: _texto_entrada(valor)
        for nome, valor in valores.items()
        if valor is not None
    }

    ausentes = [ROTULOS[n] for n, valor in valores.items() if valor is None]
    if ausentes:
        return _resultado(
            regra,
            incerta("Não dá para conferir sem: " + ", ".join(ausentes) + "."),
            usados,
        )

    try:
        veredito = regra.avaliar(valores)
        if not isinstance(veredito, Veredito):
            raise TypeError("a regra não devolveu um Veredito")
    except Exception as erro:  # noqa: BLE001 - regra com erro nunca aprova nem derruba
        return _resultado(
            regra,
            incerta(
                f"Erro interno na regra {regra.id} ({type(erro).__name__}); resultado incerto."
            ),
            usados,
        )

    sugeridas = [ROTULOS[n] for n, (_, sugerido) in resolvidas.items() if sugerido]
    if sugeridas and veredito.status is StatusRegra.APROVADA:
        veredito = Veredito(
            StatusRegra.INCERTA,
            f"Aprovada com valor sugerido pelo agente ({', '.join(sugeridas)}); "
            f"confirmar antes de seguir. {veredito.mensagem}",
            veredito.valores,
        )
    return _resultado(regra, veredito, usados)


def avaliar_regras(
    processo: Processo, ids: Iterable[str] | None = None
) -> list[ResultadoRegra]:
    """Aplica as regras (todas ou só `ids`) na ordem do repositório."""
    if ids is None:
        selecionadas = REGRAS
    else:
        pedidas = set(ids)
        desconhecidas = pedidas - _POR_ID.keys()
        if desconhecidas:
            raise ValueError(f"Regras desconhecidas: {sorted(desconhecidas)}")
        selecionadas = tuple(r for r in REGRAS if r.id in pedidas)
    return [_aplicar(regra, processo) for regra in selecionadas]


@trace("conferir")
def conferir(processo: Processo) -> list[ResultadoRegra]:
    """Aplica R01 a R08 sobre o processo completo. Sem dado suficiente -> INCERTA;
    R06 a R08 ficam NAO_VERIFICADA (fora da cobertura do MVP)."""
    resultados = avaliar_regras(processo)
    contagem: dict[str, int] = {}
    for r in resultados:
        contagem[r.status.value] = contagem.get(r.status.value, 0) + 1
    registrar_uso(
        decisao="Conferência: "
        + ", ".join(f"{n} {s}" for s, n in sorted(contagem.items()))
        + "."
    )
    return resultados
