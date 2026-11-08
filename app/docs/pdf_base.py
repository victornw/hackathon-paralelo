"""Base comum dos PDFs (Anexo A e memorial): cabeçalho, selo de simulação,
seções e campos que mostram "A INFORMAR" quando o dado falta."""

from __future__ import annotations

from datetime import datetime

from fpdf import FPDF

from app.schemas import CampoExtraido, Processo

A_INFORMAR = "A INFORMAR"

# As fontes nativas do PDF só cobrem latin-1; trocamos o que cair fora.
_TROCAS = {
    "—": "-",
    "–": "-",
    "≤": "<=",
    "≥": ">=",
    "“": '"',
    "”": '"',
    "’": "'",
    "•": "-",
}


def latin1(texto: str) -> str:
    for de, para in _TROCAS.items():
        texto = texto.replace(de, para)
    return texto.encode("latin-1", "replace").decode("latin-1")


def num(valor: float | None, casas: int | None = None) -> str:
    """Número no formato brasileiro. Sem `casas`: 5500 -> '5.500', 5.5 -> '5,5'.
    Com `casas`, decimais fixas: num(5, 2) -> '5,00'."""
    if valor is None:
        return A_INFORMAR
    if casas is None:
        if float(valor).is_integer():
            return f"{int(valor):,}".replace(",", ".")
        casas = 1
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def valor_campo(campo: CampoExtraido | None) -> str:
    if campo is None or campo.valor is None:
        return A_INFORMAR
    if isinstance(campo.valor, (int, float)):
        return num(campo.valor)
    return str(campo.valor)


def campo_conta(processo: Processo, chave: str) -> str:
    return valor_campo(processo.campos.get(chave))


def com_unidade(valor: float | None, unidade: str, casas: int | None = None) -> str:
    return A_INFORMAR if valor is None else f"{num(valor, casas)} {unidade}"


def resposta(processo: Processo, campo: str, padrao: str) -> str:
    """Resposta dada a uma pergunta do agente, ou o marcador de campo pendente."""
    return next(
        (q.resposta for q in processo.perguntas if q.campo == campo and q.resposta),
        padrao,
    )


def agora_simulado() -> datetime:
    from app.portal_sim.relogio import hoje

    return datetime.combine(hoje(), datetime.now().time())


class DocPDF(FPDF):
    def __init__(self, titulo: str, processo: Processo):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.titulo = titulo
        self.processo = processo
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(18, 18, 18)
        self.set_title(latin1(titulo))
        self.set_creator("Agente de Homologação (simulação)")
        self.add_page()

    def header(self):
        self.set_font("Helvetica", "B", 13)
        self.cell(0, 7, latin1(self.titulo), new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(90)
        self.cell(
            0,
            5,
            latin1("Enel - Norma CNC-NDBR-DBR-18-0122-EDBR v05"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_text_color(0)
        y_fim = self.get_y()
        if self.processo.simulacao:
            self.set_xy(-75, 10)
            self.set_draw_color(200, 30, 30)
            self.set_text_color(200, 30, 30)
            self.set_font("Helvetica", "B", 8)
            self.cell(
                57, 7, latin1("SIMULAÇÃO - DADOS SINTÉTICOS"), border=1, align="C"
            )
            self.set_text_color(0)
            self.set_draw_color(0)
            self.set_xy(self.l_margin, y_fim)
        self.line(
            self.l_margin, self.get_y() + 1, self.w - self.r_margin, self.get_y() + 1
        )
        self.ln(4)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(120)
        self.cell(
            0,
            5,
            latin1(f"Processo {self.processo.id} - página {self.page_no()}/{{nb}}"),
            align="C",
        )
        self.set_text_color(0)

    def secao(self, titulo: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 10)
        self.set_fill_color(235, 238, 242)
        self.cell(0, 6, latin1(titulo), fill=True, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def campo(self, rotulo: str, valor: str, largura_rotulo: float = 62):
        self.set_font("Helvetica", "B", 9)
        self.cell(largura_rotulo, 5.5, latin1(rotulo))
        destaque = valor.startswith(A_INFORMAR)
        self.set_font("Helvetica", "BI" if destaque else "", 9)
        if destaque:
            self.set_text_color(180, 90, 0)
        self.multi_cell(0, 5.5, latin1(valor), new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0)

    def paragrafo(self, texto: str, tamanho: float = 9):
        self.set_font("Helvetica", "", tamanho)
        self.multi_cell(0, 5, latin1(texto), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def tabela(
        self, cabecalho: list[str], linhas: list[list[str]], larguras: list[float]
    ):
        self.set_font("Helvetica", "B", 8.5)
        for texto, w in zip(cabecalho, larguras, strict=True):
            self.cell(w, 6, latin1(texto), border=1, fill=True)
        self.ln()
        self.set_font("Helvetica", "", 8.5)
        for linha in linhas:
            for texto, w in zip(linha, larguras, strict=True):
                self.cell(w, 6, latin1(texto), border=1)
            self.ln()

    def assinaturas(self, nomes: list[str]):
        self.ln(14)
        largura = (self.w - self.l_margin - self.r_margin) / len(nomes)
        y = self.get_y()
        for i, nome in enumerate(nomes):
            x = self.l_margin + i * largura
            self.line(x + 6, y, x + largura - 6, y)
            self.set_xy(x, y + 1)
            self.set_font("Helvetica", "", 8)
            self.multi_cell(largura, 4, latin1(nome), align="C")
        self.set_xy(self.l_margin, y + 12)
