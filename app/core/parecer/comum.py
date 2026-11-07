"""Peças comuns das regras do parecer."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas import (
    Camada,
    CampoExtraido,
    Evidencia,
    Processo,
    ResultadoRegra,
    StatusRegra,
)


def br(valor: float, casas: int = 1) -> str:
    """Número no formato brasileiro, sempre com `casas` decimais."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


@dataclass
class Parecer:
    """Acumula o raciocínio de uma regra antes de virar ResultadoRegra."""

    regra_id: str
    descricao: str
    camada: Camada
    fonte_norma: str
    valores: dict[str, float | str] = field(default_factory=dict)
    alertas: list[str] = field(default_factory=list)
    premissas: list[str] = field(default_factory=list)
    evidencias: list[Evidencia] = field(default_factory=list)

    def resultado(self, status: StatusRegra, mensagem: str) -> ResultadoRegra:
        if status == StatusRegra.APROVADA and self.premissas:
            mensagem = (
                f"{mensagem} Aprovado com premissa assumida: "
                + "; ".join(self.premissas)
                + "."
            )
        return ResultadoRegra(
            regra_id=self.regra_id,
            descricao=self.descricao,
            camada=self.camada,
            status=status,
            valores=self.valores,
            mensagem=mensagem,
            fonte_norma=self.fonte_norma,
            alertas=list(dict.fromkeys(self.alertas)),
            premissas=list(dict.fromkeys(self.premissas)),
            evidencias=self.evidencias,
        )

    def aprovada(self, mensagem: str) -> ResultadoRegra:
        return self.resultado(StatusRegra.APROVADA, mensagem)

    def reprovada(self, mensagem: str) -> ResultadoRegra:
        return self.resultado(StatusRegra.REPROVADA, mensagem)

    def incerta(self, mensagem: str) -> ResultadoRegra:
        return self.resultado(StatusRegra.INCERTA, mensagem)

    def nao_verificada(self, mensagem: str) -> ResultadoRegra:
        return self.resultado(StatusRegra.NAO_VERIFICADA, mensagem)


def numero_do_campo(campo: CampoExtraido | None) -> tuple[float | None, bool]:
    """(valor numérico, confiável). Campo ausente, vazio ou ilegível -> (None, False)."""
    if campo is None or campo.valor is None:
        return None, False
    try:
        valor = float(str(campo.valor).replace(",", "."))
    except ValueError:
        return None, False
    return valor, not campo.incerto


def texto_do_campo(processo: Processo, chave: str) -> str | None:
    campo = processo.campos.get(chave)
    if campo is None or campo.valor is None:
        return None
    return str(campo.valor)
