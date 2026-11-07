from pathlib import Path

from app.docs.gerar import gerar_documentos
from app.tracing import listar_passos


def test_gera_os_tres_documentos_e_registra_trace(processo):
    docs = gerar_documentos(processo)
    assert sorted({d.tipo for d in docs}) == [
        "memorial",
        "solicitacao_orcamento",
        "unifilar",
    ]
    assert {d.formato for d in docs if d.tipo == "unifilar"} == {"pdf", "svg"}
    for d in docs:
        assert Path(d.caminho).exists() and Path(d.caminho).stat().st_size > 0
        assert d.gerado_em.date().isoformat() == "2026-11-09"  # relógio simulado
    (passo,) = listar_passos(processo.id)
    assert passo.passo == "gerar_documentos" and passo.erro is None
    assert "4 documentos" in passo.decisao
