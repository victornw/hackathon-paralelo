"""Diagrama unifilar da microgeração FV (Enel CE), a partir de templates SVG.

Base: norma Enel CNC-NDBR-DBR-18-0122, Anexo B, conexão à BT através de
inversor (forma de conexão 1). Há um template por número de MPPTs usados
(1 ou 2). O preenchimento é por substituição de placeholders ``{{nome}}``;
todo valor é escapado para XML. Valor ausente vira "A INFORMAR", nunca um
chute.

O PDF é gerado com fpdf2 (Python puro), que desenha o SVG em uma página A4
paisagem. As fontes core do PDF (Helvetica) só cobrem latin-1, então a cópia
do SVG usada no PDF troca os poucos caracteres fora dessa faixa (ex.: "—").
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from xml.sax.saxutils import escape

from fpdf import FPDF

from app.schemas import CampoExtraido, Kit, Processo, StringFV

A_INFORMAR = "A INFORMAR"
SUFIXO_SUGERIDA = "(sugerida — confirmar)"

PASTA_TEMPLATES = Path(__file__).parent / "templates"
TEMPLATES = {
    1: PASTA_TEMPLATES / "unifilar_1mppt.svg",
    2: PASTA_TEMPLATES / "unifilar_2mppt.svg",
}

_MARCA_A_INFORMAR = '<tspan fill="#c62828" font-weight="bold">A INFORMAR</tspan>'
_SELO = re.compile(r"<!--SELO_INICIO-->.*?<!--SELO_FIM-->", re.DOTALL)
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")

# Caracteres fora do latin-1 usados nos textos -> equivalentes para o PDF.
_TROCAS_PDF = {
    "—": "-",  # travessão
    "–": "-",
    "→": "->",
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "…": "...",
}

_LIGACAO = {
    "monofasico": "monofásica",
    "bifasico": "bifásica",
    "trifasico": "trifásica",
}
_RAMAL = {"aereo": "aéreo", "subterraneo": "subterrâneo"}


# ---------------------------------------------------------------------------
# Formatação
# ---------------------------------------------------------------------------


def _num(valor: float) -> str:
    """Número no padrão brasileiro: 5,5 / 6 / 5.000 / 2,25."""
    v = round(float(valor), 2)
    if v.is_integer():
        return f"{int(v):,}".replace(",", ".")
    inteiro, _, frac = f"{v:.2f}".rstrip("0").partition(".")
    return f"{int(inteiro):,}".replace(",", ".") + "," + frac


def _num_ou_none(valor: object) -> str | None:
    """Formata número; texto passa direto; ausente vira None."""
    if valor is None:
        return None
    if isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, (int, float)):
        return _num(valor)
    texto = str(valor).strip()
    if not texto:
        return None
    try:
        return _num(float(texto.replace(",", ".")))
    except ValueError:
        return texto


def _texto(valor: str | None) -> str:
    """Escapa para XML; ausente vira o marcador A INFORMAR (em vermelho)."""
    if valor is None or not str(valor).strip():
        return _MARCA_A_INFORMAR
    return escape(str(valor))


def _campo(processo: Processo, chave: str) -> str | None:
    campo = processo.campos.get(chave)
    return _valor_campo(campo)


def _valor_campo(campo: CampoExtraido | None) -> str | None:
    if campo is None or campo.valor is None:
        return None
    texto = str(campo.valor).strip()
    return texto or None


def _com_unidade(valor: object, unidade: str) -> str | None:
    numero = _num_ou_none(valor)
    return None if numero is None else f"{numero} {unidade}"


# ---------------------------------------------------------------------------
# Template e MPPTs
# ---------------------------------------------------------------------------


def _validar_kit(processo: Processo) -> Kit:
    kit = processo.kit
    if kit is None:
        raise ValueError(
            "Não é possível gerar o unifilar: o processo ainda não tem kit (módulos e inversor)."
        )
    if kit.inversor.microinversor:
        raise ValueError(
            "Unifilar com microinversor está fora do escopo do MVP; "
            "só há templates para inversor string com 1 ou 2 MPPTs."
        )
    return kit


def _mppts_usados(kit: Kit) -> list[int]:
    """Números de MPPT na ordem; sem strings, usa os MPPTs do inversor."""
    if kit.strings:
        return sorted({s.mppt for s in kit.strings})
    return list(range(1, kit.inversor.num_mppt + 1))


def _descricao_mppt(kit: Kit, strings: list[StringFV]) -> tuple[str | None, str]:
    """(descrição da(s) string(s) no MPPT, sufixo de sugerida)."""
    if not strings:
        return None, ""
    wp = _num(kit.modulo.potencia_wp)
    if len(strings) == 1:
        desc = f"{strings[0].modulos_em_serie} módulos em série × {wp} Wp"
    else:
        series = " + ".join(str(s.modulos_em_serie) for s in strings)
        desc = f"{len(strings)} strings em paralelo ({series} módulos) × {wp} Wp"
    sugerida = SUFIXO_SUGERIDA if any(s.sugerida for s in strings) else ""
    return desc, sugerida


def _valores(processo: Processo, kit: Kit, mppts: list[int]) -> dict[str, str]:
    """Placeholder -> texto já pronto para o SVG (escapado)."""
    visita = processo.visita
    modulo = kit.modulo
    inversor = kit.inversor

    tipo_ligacao = _campo(processo, "tipo_ligacao")
    if tipo_ligacao is not None:
        tipo_ligacao = _LIGACAO.get(tipo_ligacao.lower(), tipo_ligacao)
    ramal = (
        _RAMAL.get(visita.tipo_ramal, visita.tipo_ramal) if visita.tipo_ramal else None
    )

    kwp = _num(round(kit.potencia_total_wp / 1000, 2))
    potencia_total = f"{kit.qtd_modulos} × {_num(modulo.potencia_wp)} Wp = {kwp} kWp"

    brutos: dict[str, str | None] = {
        "processo_id": processo.id,
        "titular": _campo(processo, "titular"),
        "uc": _campo(processo, "uc"),
        "endereco": _campo(processo, "endereco"),
        "cidade": _campo(processo, "cidade"),
        "classe": _campo(processo, "classe"),
        "subgrupo": _campo(processo, "subgrupo"),
        "tipo_ligacao": tipo_ligacao,
        "tensao": _com_unidade(_campo(processo, "tensao_atendimento_v"), "V"),
        "tipo_ramal": ramal,
        "disjuntor_padrao": _com_unidade(_valor_campo(visita.disjuntor_padrao_a), "A"),
        "disjuntor_ca": _com_unidade(visita.disjuntor_ca_a, "A"),
        "bitola": _com_unidade(visita.bitola_ca_mm2, "mm²"),
        "distancia": _com_unidade(visita.distancia_inversor_quadro_m, "m"),
        "inv_fabricante": inversor.fabricante,
        "inv_modelo": inversor.modelo,
        "inv_potencia": _com_unidade(inversor.potencia_nominal_w, "W"),
        "inv_tensao": _com_unidade(inversor.tensao_saida_v, "V"),
        "inv_inmetro": inversor.certificado_inmetro,
        "modulo_nome": f"{modulo.fabricante} {modulo.modelo}",
        "potencia_total": potencia_total,
    }

    valores = {chave: _texto(v) for chave, v in brutos.items()}
    for slot, mppt in enumerate(mppts, start=1):
        strings = [s for s in kit.strings if s.mppt == mppt]
        desc, sugerida = _descricao_mppt(kit, strings)
        valores[f"m{slot}_num"] = escape(str(mppt))
        valores[f"m{slot}_desc"] = _texto(desc)
        valores[f"m{slot}_sugerida"] = escape(sugerida)
    return valores


def _preencher(template: str, valores: dict[str, str], simulacao: bool) -> str:
    if not simulacao:
        template = _SELO.sub("", template)

    faltando = sorted(set(_PLACEHOLDER.findall(template)) - valores.keys())
    if faltando:
        raise KeyError(f"Placeholders sem valor no template do unifilar: {faltando}")

    return _PLACEHOLDER.sub(lambda m: valores[m.group(1)], template)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------


def _svg_para_pdf(svg: str, pdf_path: Path) -> None:
    for original, troca in _TROCAS_PDF.items():
        svg = svg.replace(original, troca)
    # Qualquer outro caractere fora do latin-1 quebraria a fonte core do PDF.
    svg = svg.encode("latin-1", errors="replace").decode("latin-1")

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(False)
    pdf.set_title("Diagrama unifilar - microgeração fotovoltaica")
    pdf.add_page()
    pdf.image(io.BytesIO(svg.encode("utf-8")), x=0, y=0, w=297, h=210)
    pdf.output(str(pdf_path))


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def gerar_unifilar(processo: Processo, pasta: Path) -> tuple[Path, Path]:
    """Preenche o template SVG do unifilar e exporta o PDF.

    Escolhe o template pelo número de MPPTs usados (MPPTs distintos em
    ``kit.strings``; sem strings, ``kit.inversor.num_mppt``). Levanta
    ValueError para kit ausente, microinversor ou mais de 2 MPPTs (fora do
    escopo do MVP). Devolve ``(svg_path, pdf_path)``.
    """
    kit = _validar_kit(processo)
    mppts = _mppts_usados(kit)
    if len(mppts) not in TEMPLATES:
        raise ValueError(
            f"Unifilar com {len(mppts)} MPPTs está fora do escopo do MVP; "
            "só há templates para 1 ou 2 MPPTs."
        )

    template = TEMPLATES[len(mppts)].read_text(encoding="utf-8")
    svg = _preencher(template, _valores(processo, kit, mppts), processo.simulacao)

    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    svg_path = pasta / f"unifilar_{processo.id}.svg"
    pdf_path = pasta / f"unifilar_{processo.id}.pdf"
    svg_path.write_text(svg, encoding="utf-8")
    _svg_para_pdf(svg, pdf_path)
    return svg_path, pdf_path
