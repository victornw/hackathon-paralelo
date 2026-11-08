"""gerar_documentos: solicitação (Anexo A), memorial e unifilar de um processo."""

from __future__ import annotations

import os
from pathlib import Path

from app.docs.anexo_a import gerar_anexo_a
from app.docs.memorial import gerar_memorial
from app.docs.pdf_base import agora_simulado
from app.schemas import DocumentoGerado, Processo
from app.tracing import registrar_uso, trace


def pasta_documentos(processo: Processo) -> Path:
    return Path(os.environ.get("DOCS_DIR", "data/docs")) / processo.id


def _doc(tipo: str, caminho: Path) -> DocumentoGerado:
    return DocumentoGerado(
        tipo=tipo,
        nome_arquivo=caminho.name,
        caminho=str(caminho),
        formato=caminho.suffix.lstrip("."),
        gerado_em=agora_simulado(),
    )


@trace("gerar_documentos")
def gerar_documentos(processo: Processo) -> list[DocumentoGerado]:
    """Gera a solicitação de orçamento (Anexo A, PDF), o memorial descritivo
    (PDF) e o unifilar (SVG + PDF). Campo ausente sai como "A INFORMAR"."""
    from app.docs.unifilar import gerar_unifilar

    pasta = pasta_documentos(processo)
    svg, pdf_unifilar = gerar_unifilar(processo, pasta)
    docs = [
        _doc("solicitacao_orcamento", gerar_anexo_a(processo, pasta)),
        _doc("memorial", gerar_memorial(processo, pasta)),
        _doc("unifilar", pdf_unifilar),
        _doc("unifilar", svg),
    ]
    from app.tracing.db import espelhar_arquivo

    for d in docs:
        espelhar_arquivo(d.caminho)  # com Turso, o PDF sobrevive ao reinício do Render
    registrar_uso(
        decisao=f"Gerados {len(docs)} documentos (Anexo A, memorial e unifilar)."
    )
    return docs
