"""R05: certificação INMETRO do inversor (Portaria 140/2022) em cascata.

Do mais automático para o mais manual; o engenheiro só entra quando o sistema
não consegue provar sozinho:

1. Consulta ao INMETRO pelo número do registro: registro ativo, modelo incluído e
   "220 V" na descrição atual -> APROVADA, com link e data da consulta.
2. Catálogo verificado (inmetro_verificados.json): alguém conferiu o certificado
   uma vez à mão e registrou nome, data e fonte -> APROVADA, com essa verificação
   como fonte. Entradas sem `verificado_por` são candidatas e não contam.
3. Registro ativo e modelo incluído, mas sem tensão na descrição, e o datasheet
   diz 220 V -> INCERTA com as duas evidências; o engenheiro confirma com um
   clique (confirmado_por/em) e assume. Confirmada, não bloqueia.
4. Registro inativo ou modelo fora do registro -> REPROVADA (bloqueia).

Sem consulta possível (site fora do ar, número ausente ou sintético) e fora do
catálogo, a regra fica INCERTA: o produto nunca diz "verificado" sem ter verificado.
A consulta tem timeout curto e cache local; a demo não depende do site.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.core.parecer.comum import Parecer
from app.schemas import Camada, Evidencia, Processo, ResultadoRegra, StatusRegra

POTENCIA_MAX_PORTARIA_W = 75_000
TENSAO_CONEXAO_V = 220
TIMEOUT_S = 6
VALIDADE_CACHE = timedelta(days=7)
CATALOGO = Path(__file__).with_name("inmetro_verificados.json")
URL_DETALHE = (
    "https://registro.inmetro.gov.br/consulta/detalhe.aspx?NumeroRegistro={}&pag=1"
)

FONTE = "Portaria INMETRO 140/2022; Norma Enel, Tabelas 10 e 11"

_ESQUEMA_CACHE = """
CREATE TABLE IF NOT EXISTS inmetro_consultas (
    numero TEXT PRIMARY KEY,
    json TEXT NOT NULL
)
"""


# ---------------------------------------------------------------------------
# Consulta e leitura da página
# ---------------------------------------------------------------------------


@dataclass
class ModeloRegistrado:
    marca: str
    modelo: str
    descricao: str
    data: str


@dataclass
class Consulta:
    numero: str
    url: str
    consultado_em: datetime
    status: str | None  # "Ativo", "Cancelado", "Suspenso"...
    incluidos: list[ModeloRegistrado] = field(default_factory=list)
    sha256: str = ""


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", sem_acento.lower())


def _linhas(pagina_html: str) -> list[str]:
    t = re.sub(
        r"(?is)<script.*?</script>|<style.*?</style>|<head.*?</head>", "", pagina_html
    )
    t = re.sub(r"(?i)<br\s*/?>|</tr>|</p>|</div>|</table>", "\n", t)
    t = re.sub(r"(?i)</td>|</th>", " | ", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    celulas = (
        re.sub(r"\s+", " ", celula).strip()
        for linha in t.split("\n")
        for celula in linha.split(" | ")
    )
    return [c.strip(" |") for c in celulas if c.strip(" |")]


def ler_pagina(numero: str, url: str, pagina_html: str, quando: datetime) -> Consulta:
    """Extrai status e modelos incluídos. Guarda só dados técnicos (sem contatos)."""
    linhas = _linhas(pagina_html)
    status = None
    for i, linha in enumerate(linhas[:-1]):
        if linha == "Status":
            status = linhas[i + 1]
            break
    incluidos: list[ModeloRegistrado] = []
    excluidos: set[tuple[str, str]] = set()
    if "Código de barras" in linhas:
        resto = linhas[linhas.index("Código de barras") + 1 :]
        i = 0
        while i + 4 < len(resto) and re.fullmatch(r"\d{2}/\d{2}/\d{4}", resto[i]):
            data, alteracao, marca, modelo, descricao = resto[i : i + 5]
            registro = ModeloRegistrado(marca, modelo, descricao, data)
            if alteracao.lower().startswith("inclu"):
                incluidos.append(registro)
            else:
                excluidos.add((_normalizar(modelo), _normalizar(descricao)))
            i += 5
    incluidos = [
        m
        for m in incluidos
        if (_normalizar(m.modelo), _normalizar(m.descricao)) not in excluidos
    ]
    return Consulta(
        numero=numero,
        url=url,
        consultado_em=quando,
        status=status,
        incluidos=incluidos,
        sha256=hashlib.sha256(pagina_html.encode("utf-8", "replace")).hexdigest(),
    )


def _baixar(url: str) -> str:
    pedido = Request(
        url, headers={"User-Agent": "homologacao-solar/0.1 (consulta pontual)"}
    )
    with urlopen(pedido, timeout=TIMEOUT_S) as resposta:
        return resposta.read().decode("utf-8", "replace")


def _agora() -> datetime:
    from app.portal_sim.relogio import hoje

    return datetime.combine(hoje(), datetime.now().time())


def _cache_ler(numero: str) -> Consulta | None:
    from app.tracing.db import conectar

    with conectar() as con:
        con.execute(_ESQUEMA_CACHE)
        linha = con.execute(
            "SELECT json FROM inmetro_consultas WHERE numero = ?", (numero,)
        ).fetchone()
    if linha is None:
        return None
    d = json.loads(linha[0])
    c = Consulta(
        numero=d["numero"],
        url=d["url"],
        consultado_em=datetime.fromisoformat(d["consultado_em"]),
        status=d["status"],
        incluidos=[ModeloRegistrado(**m) for m in d["incluidos"]],
        sha256=d["sha256"],
    )
    return c if _agora() - c.consultado_em <= VALIDADE_CACHE else None


def _cache_gravar(c: Consulta) -> None:
    from app.tracing.db import conectar

    d = {
        "numero": c.numero,
        "url": c.url,
        "consultado_em": c.consultado_em.isoformat(),
        "status": c.status,
        "incluidos": [m.__dict__ for m in c.incluidos],
        "sha256": c.sha256,
    }
    with conectar() as con:
        con.execute(_ESQUEMA_CACHE)
        con.execute(
            "INSERT INTO inmetro_consultas (numero, json) VALUES (?, ?) "
            "ON CONFLICT(numero) DO UPDATE SET json = excluded.json",
            (c.numero, json.dumps(d, ensure_ascii=False)),
        )


def consultar_registro(numero: str) -> Consulta | None:
    """Consulta o detalhe do registro (cache de 7 dias). None se o site não responder."""
    cache = _cache_ler(numero)
    if cache is not None:
        return cache
    url = URL_DETALHE.format(quote(numero, safe=""))
    try:
        pagina = _baixar(url)
    except (OSError, ValueError):  # rede, timeout, HTTP: cai no passo seguinte
        return None
    consulta = ler_pagina(numero, url, pagina, _agora())
    if consulta.status is None:
        return None  # página fora do formato esperado: não arriscar leitura
    _cache_gravar(consulta)
    return consulta


# ---------------------------------------------------------------------------
# Catálogo verificado à mão
# ---------------------------------------------------------------------------


def catalogo_verificado() -> list[dict]:
    if not CATALOGO.is_file():
        return []
    entradas = json.loads(CATALOGO.read_text(encoding="utf-8"))["inversores"]
    return [e for e in entradas if e.get("verificado_por") and e.get("verificado_em")]


def _no_catalogo(fabricante: str, modelo: str, registro: str | None) -> dict | None:
    for e in catalogo_verificado():
        if _normalizar(e["modelo"]) != _normalizar(modelo):
            continue
        if _normalizar(e["fabricante"]) != _normalizar(fabricante):
            continue
        if (
            registro
            and e.get("registro")
            and _normalizar(e["registro"]) != _normalizar(registro)
        ):
            continue
        if e.get("tensao_v") == TENSAO_CONEXAO_V:
            return e
    return None


# ---------------------------------------------------------------------------
# A regra
# ---------------------------------------------------------------------------


def _tem_220v(descricao: str) -> bool:
    return re.search(r"(?<!\d)220\s*(/\s*\d+\s*)?v", descricao.lower()) is not None


def _confirmacao_anterior(processo: Processo, chave: str) -> ResultadoRegra | None:
    for r in processo.regras:
        if (
            r.regra_id == "R05"
            and r.confirmado_por
            and r.valores.get("chave_confirmacao") == chave
        ):
            return r
    return None


def avaliar(processo: Processo) -> ResultadoRegra:
    p = Parecer(
        "R05",
        "Inversor com registro INMETRO ativo para a tensão de conexão (220 V)",
        Camada.DISTRIBUIDORA,
        FONTE,
    )
    if processo.kit is None:
        return p.incerta("Kit ausente.")
    inv = processo.kit.inversor
    if inv.potencia_nominal_w > POTENCIA_MAX_PORTARIA_W:
        return p.nao_verificada(
            "Inversor acima de 75 kW: fora da exigência da Portaria 140."
        )
    numero = (inv.certificado_inmetro or "").strip() or None
    p.valores.update({"modelo": inv.modelo, "registro": numero or "não informado"})

    # 1. consulta automática
    consulta = None
    if numero and not numero.upper().startswith("SIMULADO"):
        consulta = consultar_registro(numero)
        if consulta is None:
            p.alertas.append(
                "Consulta ao INMETRO indisponível agora; usado o catálogo."
            )
    elif numero:
        p.alertas.append("Número de registro sintético: não há consulta ao INMETRO.")

    modelo_registrado = None
    if consulta is not None:
        alvo = _normalizar(inv.modelo)
        modelo_registrado = next(
            (m for m in consulta.incluidos if _normalizar(m.modelo) == alvo), None
        )
        p.evidencias.append(
            Evidencia(
                descricao=(
                    f"Registro {numero}: situação {consulta.status}; modelo "
                    + ("incluído" if modelo_registrado else "não encontrado")
                ),
                fonte="INMETRO (consulta automática)",
                url=consulta.url,
                consultado_em=consulta.consultado_em,
                trecho=modelo_registrado.descricao if modelo_registrado else None,
            )
        )
        if (consulta.status or "").lower() != "ativo":
            return p.reprovada(
                f"Registro INMETRO {numero} com situação '{consulta.status}': não serve "
                "para a conexão."
            )
        if modelo_registrado is None:
            return p.reprovada(
                f"Modelo {inv.modelo} não aparece entre os modelos incluídos no registro {numero}."
            )
        if _tem_220v(modelo_registrado.descricao):
            return p.aprovada(
                f"INMETRO confirma registro {numero} ativo, modelo {inv.modelo} e 220 V na "
                f"descrição (consulta em {consulta.consultado_em:%d/%m/%Y})."
            )

    # 2. catálogo verificado à mão
    entrada = _no_catalogo(inv.fabricante, inv.modelo, numero)
    if entrada is not None:
        p.evidencias.append(
            Evidencia(
                descricao=(
                    f"Certificado conferido à mão por {entrada['verificado_por']} em "
                    f"{entrada['verificado_em']}: {entrada.get('observacao', '220 V')}"
                ),
                fonte="catálogo verificado",
                url=entrada.get("url_certificado") or entrada.get("url_registro"),
            )
        )
        return p.aprovada(
            f"Inversor {inv.fabricante} {inv.modelo} no catálogo verificado: certificado para "
            f"220 V conferido por {entrada['verificado_por']} em {entrada['verificado_em']}."
        )

    # 3. registro ativo sem tensão + datasheet 220 V: o engenheiro confirma
    if modelo_registrado is not None and inv.tensao_saida_v == TENSAO_CONEXAO_V:
        p.evidencias.append(
            Evidencia(
                descricao=f"Datasheet do inversor: tensão de saída {TENSAO_CONEXAO_V} V",
                fonte="datasheet",
            )
        )
        chave = f"{numero}|{_normalizar(inv.modelo)}|{consulta.sha256[:16]}"
        p.valores.update({"confirmavel": "sim", "chave_confirmacao": chave})
        resultado = p.incerta(
            f"Registro {numero} ativo e modelo incluído, mas a descrição no INMETRO não "
            "cita a tensão; o datasheet diz 220 V. Confirme na revisão para assumir."
        )
        anterior = _confirmacao_anterior(processo, chave)
        if anterior is not None:
            resultado.confirmado_por = anterior.confirmado_por
            resultado.confirmado_em = anterior.confirmado_em
            resultado.mensagem += (
                f" Confirmado por {anterior.confirmado_por} em "
                f"{anterior.confirmado_em:%d/%m/%Y}."
            )
        return resultado

    if not numero:
        return p.incerta("Informe o número do registro INMETRO do inversor.")
    return p.incerta(
        "Não foi possível comprovar o registro INMETRO para 220 V; confira o certificado "
        "e registre no catálogo verificado."
    )


def confirmar(processo: Processo, engenheiro: str) -> Processo:
    """Confirmação do engenheiro (passo 3). Só vale para R05 confirmável."""
    nome = engenheiro.strip()
    if not nome:
        raise ValueError("Informe o nome do engenheiro que confirma.")
    alvo = next(
        (
            r
            for r in processo.regras
            if r.regra_id == "R05" and r.valores.get("confirmavel") == "sim"
        ),
        None,
    )
    if alvo is None or alvo.status != StatusRegra.INCERTA:
        raise ValueError(
            "A R05 deste processo não está aguardando confirmação do engenheiro."
        )
    alvo.confirmado_por = nome
    alvo.confirmado_em = _agora()
    return processo


def bloqueia(resultado: ResultadoRegra) -> bool:
    """Para a política de aprovação: R05 incerta confirmada pelo engenheiro não bloqueia."""
    if resultado.status == StatusRegra.APROVADA:
        return False
    if resultado.status == StatusRegra.INCERTA and resultado.confirmado_por:
        return resultado.valores.get("confirmavel") != "sim"
    return True


__all__ = ["avaliar", "bloqueia", "confirmar", "consultar_registro", "ler_pagina"]
