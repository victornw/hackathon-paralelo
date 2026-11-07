import pytest

from app.portal_sim.pendencias import (
    CATEGORIAS,
    classificar_pendencia,
    classificar_por_palavras,
)
from app.portal_sim.portal import MOTIVO_PENDENCIA_ROTEIRO


@pytest.mark.parametrize(
    ("texto", "categoria"),
    [
        (MOTIVO_PENDENCIA_ROTEIRO, "unifilar_inconsistente"),
        ("Titular divergente entre o formulário e o memorial.", "dados_divergentes"),
        ("Procuração ausente.", "documentacao_incompleta"),
        ("ART sem comprovante de quitação.", "art_irregular"),
        ("Inversor sem certificado INMETRO para 220 V.", "inversor_certificacao"),
        ("Coordenadas informadas não correspondem ao local.", "localizacao"),
        ("Padrão de entrada fora da norma de fornecimento.", "padrao_entrada"),
        ("Favor entrar em contato com a central.", "outros"),
    ],
)
def test_linha_de_base(texto, categoria):
    assert classificar_por_palavras(texto) == categoria


def test_contrato_devolve_categoria_e_correcao():
    categoria, correcao = classificar_pendencia(MOTIVO_PENDENCIA_ROTEIRO)
    assert categoria in CATEGORIAS
    assert "unifilar" in correcao.lower()


def test_toda_categoria_tem_correcao_e_descricao():
    for cat in CATEGORIAS.values():
        assert cat["correcao"] and cat["descricao"]
