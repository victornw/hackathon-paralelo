"""Extração de dados dos documentos: conta de luz, kit vendido e foto do padrão.

O LLM só lê. A confiança de cada campo é calculada aqui: o que o modelo diz
vale no máximo 0,95, e cai se o trecho citado não existe no texto de origem,
se o valor não sai do trecho ou se o formato/faixa não confere. Na leitura por
visão o teto é 0,8. Campo ilegível volta com valor None e confiança 0.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import cache
from pathlib import Path

from pydantic import BaseModel, Field, create_model
from pypdf import PdfReader

from app.core.llm import completar_json, disponivel
from app.schemas import (
    CampoExtraido,
    DadosVisita,
    Fonte,
    Inversor,
    Kit,
    Modulo,
    StringFV,
)
from app.tracing import registrar_uso, trace

CHAVES_CONTA = (
    "uc",
    "titular",
    "cpf_cnpj",
    "endereco",
    "cidade",
    "classe",
    "subgrupo",
    "tipo_ligacao",
    "tensao_atendimento_v",
    "consumo_medio_kwh",
)

TETO = 0.95
TETO_VISAO = 0.8
TETO_TRECHO_NAO_CONFERE = 0.5
TETO_FORMATO = 0.3
LIMIAR_CONFIAVEL = 0.8
MIN_CARACTERES_TEXTO = 200
MAX_IMAGENS = 3
MAX_CARACTERES_PROMPT = 15000
MOTIVO_SEM_LEITURA = "sem camada de texto e sem modelo de visão"

EXTENSOES_IMAGEM = {".png", ".jpg", ".jpeg", ".webp"}
CATALOGO = Path(__file__).with_name("catalogo.json")

_DESCRICAO_CAMPOS = {
    "uc": "código da unidade consumidora, só dígitos",
    "titular": "nome do titular",
    "cpf_cnpj": "CPF ou CNPJ do titular, como impresso",
    "endereco": "endereço da unidade consumidora",
    "cidade": "só o nome da cidade, sem UF nem estado (ex.: CAUCAIA, não CAUCAIA - CE)",
    "classe": "classe de consumo (ex.: Residencial)",
    "subgrupo": "subgrupo tarifário (ex.: B1)",
    "tipo_ligacao": "monofasico, bifasico ou trifasico",
    "tensao_atendimento_v": "tensão de atendimento em volts (número)",
    "consumo_medio_kwh": "consumo médio mensal em kWh (número)",
}

_LIGACOES = {"mono": "monofasico", "bi": "bifasico", "tri": "trifasico"}
_POLOS = {"uni": 1, "mono": 1, "bi": 2, "tri": 3}


class KitIncompleto(Exception):
    def __init__(self, faltando: list[str]):
        super().__init__(f"kit incompleto, faltam: {', '.join(faltando)}")
        self.faltando = faltando


class _CampoLLM(BaseModel):
    valor: str | float | int | None = None
    confianca: float | None = None
    trecho: str | None = None


_ContaLLM = create_model(
    "_ContaLLM",
    **{c: (_CampoLLM, Field(default_factory=_CampoLLM)) for c in CHAVES_CONTA},
)


class _PadraoLLM(BaseModel):
    disjuntor_padrao_a: _CampoLLM = Field(default_factory=_CampoLLM)
    polos_padrao: _CampoLLM = Field(default_factory=_CampoLLM)


class _EspecModulo(BaseModel):
    potencia_wp: float | None = None
    voc_v: float | None = None
    isc_a: float | None = None
    vmp_v: float | None = None
    imp_a: float | None = None
    coef_temp_voc_pct_c: float | None = None


class _EspecInversor(BaseModel):
    potencia_nominal_w: float | None = None
    potencia_max_cc_w: float | None = None
    tensao_max_cc_v: float | None = None
    mppt_min_v: float | None = None
    mppt_max_v: float | None = None
    num_mppt: int | None = None
    corrente_max_entrada_a: float | None = None
    corrente_max_saida_a: float | None = None
    tensao_saida_v: float | None = None
    microinversor: bool | None = None
    certificado_inmetro: str | None = None


class _StringLLM(BaseModel):
    mppt: int
    modulos_em_serie: int


class _KitLLM(BaseModel):
    fabricante_modulo: str | None = None
    modelo_modulo: str | None = None
    qtd_modulos: int | None = None
    fabricante_inversor: str | None = None
    modelo_inversor: str | None = None
    strings: list[_StringLLM] = []
    especificacoes_modulo: _EspecModulo = Field(default_factory=_EspecModulo)
    especificacoes_inversor: _EspecInversor = Field(default_factory=_EspecInversor)


# ---------------------------------------------------------------------------
# Texto e números
# ---------------------------------------------------------------------------


def _norm(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower()


def _compacto(texto: str) -> str:
    return re.sub(r"\s+", "", _norm(texto))


def _alfanumerico(texto: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _norm(texto).replace("(sintetico)", ""))


_NUMERO = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?")


def _numeros(texto: str) -> list[float]:
    achados = []
    for bruto in _NUMERO.findall(texto):
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", bruto):
            bruto = bruto.replace(".", "")
        achados.append(float(bruto.replace(",", ".")))
    return achados


def _numero(valor: object) -> float | None:
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        achados = _numeros(valor)
        return achados[0] if achados else None
    return None


def _ligacao(texto: str) -> str | None:
    achado = re.search(r"\b(mono|bi|tri)-?fas", _norm(texto))
    return _LIGACOES[achado.group(1)] if achado else None


def _polos(texto: str) -> int | None:
    n = _norm(texto)
    achado = re.search(r"\b(uni|mono|bi|tri)-?polar", n)
    if achado:
        return _POLOS[achado.group(1)]
    achado = re.search(r"\b([123])\s?(?:p\b|polos?\b)", n)
    return int(achado.group(1)) if achado else None


def _digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto)


# ---------------------------------------------------------------------------
# Validação e confiança calculada
# ---------------------------------------------------------------------------


def _normalizar_valor(chave: str, valor: object) -> str | float | int | None:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    if isinstance(valor, float) and valor.is_integer() and chave == "uc":
        valor = int(valor)
    if chave in {
        "tensao_atendimento_v",
        "consumo_medio_kwh",
        "disjuntor_padrao_a",
        "polos_padrao",
    }:
        n = _numero(valor)
        if n is None:
            return str(valor).strip()
        return int(n) if n.is_integer() else n
    texto = str(valor).strip()
    if chave == "uc":
        return _digitos(texto) if re.fullmatch(r"[\d\s./-]+", texto) else texto
    if chave == "tipo_ligacao":
        return _ligacao(texto) or texto
    if chave == "subgrupo":
        return re.sub(r"\s+", "", texto).upper()
    return texto


def _formato_ok(chave: str, valor: object) -> bool:
    texto = str(valor)
    if chave == "uc":
        return re.fullmatch(r"\d{6,12}", texto) is not None
    if chave == "tipo_ligacao":
        return valor in _LIGACOES.values()
    if chave == "tensao_atendimento_v":
        return _numero(valor) in {127, 220, 380}
    if chave == "subgrupo":
        return re.fullmatch(r"B[1-4]", texto) is not None
    if chave == "cpf_cnpj":
        return re.fullmatch(r"[\d*.\-/\s]+", texto) is not None and len(
            re.sub(r"[^\d*]", "", texto)
        ) in (11, 14)
    if chave == "consumo_medio_kwh":
        n = _numero(valor)
        return isinstance(valor, (int, float)) and n is not None and 0 < n <= 100_000
    if chave == "disjuntor_padrao_a":
        n = _numero(valor)
        return isinstance(valor, (int, float)) and n is not None and 0 < n <= 200
    if chave == "polos_padrao":
        return valor in (1, 2, 3)
    return True


def _derivavel(chave: str, valor: object, trecho: str) -> bool:
    if chave == "tipo_ligacao":
        return _ligacao(trecho) == valor
    if chave == "polos_padrao":
        return _polos(trecho) == valor
    if chave in {"uc", "cpf_cnpj"}:
        digitos = _digitos(str(valor))
        return bool(digitos) and digitos in _digitos(trecho)
    if chave in {"tensao_atendimento_v", "consumo_medio_kwh", "disjuntor_padrao_a"}:
        n = _numero(valor)
        return n is not None and any(abs(n - x) < 1e-6 for x in _numeros(trecho))
    return _compacto(str(valor)) in _compacto(trecho)


def _confianca(
    chave: str,
    valor: object,
    bruta: float | None,
    trecho: str | None,
    fonte_compacta: str | None,
    via_visao: bool,
) -> float:
    c = min(max(bruta or 0.0, 0.0), TETO)
    if via_visao:
        c = min(c, TETO_VISAO)
    if not trecho:
        c = min(c, TETO_TRECHO_NAO_CONFERE)
    else:
        if fonte_compacta is not None and _compacto(trecho) not in fonte_compacta:
            c = min(c, TETO_TRECHO_NAO_CONFERE)
        if not _derivavel(chave, valor, trecho):
            c = min(c, TETO_TRECHO_NAO_CONFERE)
    if not _formato_ok(chave, valor):
        c = min(c, TETO_FORMATO)
    return round(c, 2)


def _campo(
    chave: str,
    bruto: _CampoLLM,
    documento: str,
    paginas_compactas: list[str] | None,
    via_visao: bool,
) -> CampoExtraido:
    valor = _normalizar_valor(chave, bruto.valor)
    if valor is None:
        return CampoExtraido(
            valor=None, confianca=0.0, fonte=Fonte(documento=documento)
        )
    fonte_compacta = (
        "".join(paginas_compactas) if paginas_compactas is not None else None
    )
    confianca = _confianca(
        chave, valor, bruto.confianca, bruto.trecho, fonte_compacta, via_visao
    )
    pagina = None
    if bruto.trecho and paginas_compactas:
        alvo = _compacto(bruto.trecho)
        pagina = next(
            (i for i, p in enumerate(paginas_compactas, 1) if alvo in p), None
        )
    return CampoExtraido(
        valor=valor,
        confianca=confianca,
        fonte=Fonte(documento=documento, pagina=pagina, trecho=bruto.trecho),
    )


# ---------------------------------------------------------------------------
# Leitura de arquivos
# ---------------------------------------------------------------------------


def _paginas_pdf(arquivo: Path) -> list[str]:
    return [p.extract_text() or "" for p in PdfReader(arquivo).pages]


def _imagens_pdf(arquivo: Path) -> list[bytes]:
    imagens: list[bytes] = []
    for pagina in PdfReader(arquivo).pages:
        for imagem in pagina.images:
            imagens.append(imagem.data)
            if len(imagens) == MAX_IMAGENS:
                return imagens
    return imagens


def _texto_para_prompt(paginas: list[str]) -> str:
    partes = [f"[Página {i}]\n{t.strip()}" for i, t in enumerate(paginas, 1)]
    return "\n\n".join(partes)[:MAX_CARACTERES_PROMPT]


# ---------------------------------------------------------------------------
# Conta de luz
# ---------------------------------------------------------------------------

_SISTEMA_CONTA = (
    "Você lê contas de luz da distribuidora e extrai campos. Nunca invente: se o campo não "
    "estiver legível, use valor null e confianca 0. Para cada campo devolva valor, confianca "
    "(0 a 1) e trecho, que é uma cópia literal e curta do texto onde o valor aparece. "
    "Campos:\n" + "\n".join(f"- {c}: {d}" for c, d in _DESCRICAO_CAMPOS.items())
)


def _vazio(documento: str, motivo: str) -> dict[str, CampoExtraido]:
    return {
        c: CampoExtraido(
            valor=None, confianca=0.0, fonte=Fonte(documento=documento, trecho=motivo)
        )
        for c in CHAVES_CONTA
    }


def _montar_conta(
    resposta: BaseModel,
    documento: str,
    paginas_compactas: list[str] | None,
    via_visao: bool,
) -> dict[str, CampoExtraido]:
    return {
        c: _campo(c, getattr(resposta, c), documento, paginas_compactas, via_visao)
        for c in CHAVES_CONTA
    }


@trace("extrair_conta")
def extrair_conta(arquivo: Path) -> dict[str, CampoExtraido]:
    arquivo = Path(arquivo)
    sufixo = arquivo.suffix.lower()
    if sufixo != ".pdf" and sufixo not in EXTENSOES_IMAGEM:
        raise ValueError(f"formato não suportado: {arquivo.name}")

    paginas = _paginas_pdf(arquivo) if sufixo == ".pdf" else []
    if sum(len(p.strip()) for p in paginas) >= MIN_CARACTERES_TEXTO:
        resposta = completar_json(
            "extracao", _SISTEMA_CONTA, _texto_para_prompt(paginas), _ContaLLM
        )
        campos = _montar_conta(
            resposta, arquivo.name, [_compacto(p) for p in paginas], False
        )
        via = "texto"
    else:
        imagens = _imagens_pdf(arquivo) if sufixo == ".pdf" else [arquivo.read_bytes()]
        if imagens and disponivel("visao"):
            resposta = completar_json(
                "visao",
                _SISTEMA_CONTA,
                "Leia a conta de luz nas imagens.",
                _ContaLLM,
                imagens,
            )
            campos = _montar_conta(resposta, arquivo.name, None, True)
            via = "visão"
        else:
            campos = _vazio(arquivo.name, MOTIVO_SEM_LEITURA)
            via = "sem leitura"

    confiaveis = sum(1 for c in campos.values() if not c.incerto)
    registrar_uso(
        decisao=f"Conta lida por {via}: {confiaveis} de {len(campos)} campos com confiança >= 0,8."
    )
    return campos


# ---------------------------------------------------------------------------
# Kit
# ---------------------------------------------------------------------------

_SISTEMA_KIT = (
    "Você lê propostas comerciais e datasheets de sistemas fotovoltaicos. Nunca invente: o que não "
    "estiver escrito nos documentos fica null. Extraia fabricante e modelo do módulo e do inversor, "
    "a quantidade de módulos e, só se estiverem explícitas, as strings (mppt e módulos em série). "
    "Em especificacoes_modulo e especificacoes_inversor, preencha apenas valores que constem nos "
    "documentos, nas unidades dos nomes dos campos (W, V, A)."
)


@cache
def _catalogo() -> dict[str, list[dict]]:
    return json.loads(CATALOGO.read_text(encoding="utf-8"))


def _buscar(lista: list[dict], modelo: str | None) -> dict | None:
    consulta = _alfanumerico(modelo or "")
    if len(consulta) < 4:
        return None
    for item in lista:
        chave = _alfanumerico(item["modelo"])
        if chave in consulta or consulta in chave:
            return item
    return None


def _com_valores(dados: dict[str, object]) -> dict[str, object]:
    return {k: v for k, v in dados.items() if v is not None}


def _montar_modulo(lido: _KitLLM, faltando: list[str]) -> Modulo | None:
    modelo = lido.modelo_modulo
    do_catalogo = _buscar(_catalogo()["modulos"], modelo)
    if do_catalogo:
        return Modulo(**do_catalogo)
    dados = _com_valores(
        {"fabricante": lido.fabricante_modulo, "modelo": modelo}
        | lido.especificacoes_modulo.model_dump()
    )
    obrigatorios = ("fabricante", "modelo", "potencia_wp", "voc_v", "isc_a")
    ausentes = [f"modulo.{c}" for c in obrigatorios if c not in dados]
    faltando += ausentes
    return None if ausentes else Modulo(**dados)


def _montar_inversor(lido: _KitLLM, faltando: list[str]) -> Inversor | None:
    modelo = lido.modelo_inversor
    do_catalogo = _buscar(_catalogo()["inversores"], modelo)
    if do_catalogo:
        return Inversor(**do_catalogo)
    dados = _com_valores(
        {"fabricante": lido.fabricante_inversor, "modelo": modelo}
        | lido.especificacoes_inversor.model_dump()
    )
    obrigatorios = (
        "fabricante",
        "modelo",
        "potencia_nominal_w",
        "potencia_max_cc_w",
        "tensao_max_cc_v",
        "corrente_max_saida_a",
    )
    ausentes = [f"inversor.{c}" for c in obrigatorios if c not in dados]
    faltando += ausentes
    return None if ausentes else Inversor(**dados)


def _modelo_no_texto(modelo: str | None, texto_alfanumerico: str) -> str | None:
    """Descarta modelo que o LLM citou mas que não aparece nos documentos."""
    if modelo and _alfanumerico(modelo) in texto_alfanumerico:
        return modelo
    return None


@trace("extrair_kit")
def extrair_kit(arquivos: list[Path]) -> Kit:
    blocos = [
        f"=== {Path(a).name} ===\n{_texto_para_prompt(_paginas_pdf(Path(a)))}"
        for a in arquivos
    ]
    texto = "\n\n".join(blocos)
    texto_alfanumerico = _alfanumerico(texto)
    if len(texto_alfanumerico) < 20:
        raise KitIncompleto(["modulo", "qtd_modulos", "inversor"])

    lido = completar_json(
        "extracao", _SISTEMA_KIT, texto[:MAX_CARACTERES_PROMPT], _KitLLM
    )
    lido.modelo_modulo = _modelo_no_texto(lido.modelo_modulo, texto_alfanumerico)
    lido.modelo_inversor = _modelo_no_texto(lido.modelo_inversor, texto_alfanumerico)

    faltando: list[str] = []
    modulo = _montar_modulo(lido, faltando)
    inversor = _montar_inversor(lido, faltando)
    if not lido.qtd_modulos or lido.qtd_modulos < 1:
        faltando.append("qtd_modulos")
    if faltando:
        raise KitIncompleto(faltando)

    strings = [
        StringFV(mppt=s.mppt, modulos_em_serie=s.modulos_em_serie)
        for s in lido.strings
        if s.mppt >= 1 and s.modulos_em_serie >= 1
    ]
    kit = Kit(
        modulo=modulo, qtd_modulos=lido.qtd_modulos, inversor=inversor, strings=strings
    )
    registrar_uso(
        decisao=(
            f"Kit lido: {kit.qtd_modulos} x {modulo.modelo} com {inversor.modelo}; "
            f"{len(strings)} string(s) explícita(s)."
        )
    )
    return kit


# ---------------------------------------------------------------------------
# Padrão de entrada
# ---------------------------------------------------------------------------

_SISTEMA_PADRAO = (
    "Você lê a foto do padrão de entrada de uma unidade consumidora. Leia a corrente do disjuntor "
    "geral (em A) e o número de polos (1, 2 ou 3). Nunca invente: se não estiver legível, use valor "
    "null e confianca 0. Em trecho, copie o que está escrito no disjuntor ou descreva o que viu."
)


@trace("extrair_padrao")
def extrair_padrao(foto: Path) -> DadosVisita:
    foto = Path(foto)
    if not disponivel("visao"):
        registrar_uso(
            decisao="Sem modelo de visão: padrão não lido, as perguntas cobrem."
        )
        return DadosVisita()
    resposta = completar_json(
        "visao",
        _SISTEMA_PADRAO,
        "Leia o disjuntor geral na foto.",
        _PadraoLLM,
        [foto.read_bytes()],
    )
    disjuntor = _campo(
        "disjuntor_padrao_a", resposta.disjuntor_padrao_a, foto.name, None, True
    )
    polos = _campo("polos_padrao", resposta.polos_padrao, foto.name, None, True)
    registrar_uso(
        decisao=f"Padrão lido: disjuntor {disjuntor.valor} A, {polos.valor} polo(s)."
    )
    return DadosVisita(disjuntor_padrao_a=disjuntor, polos_padrao=polos)
