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


def _rodar(texto, processo_id):
    from app.tracing import processo_atual

    with processo_atual(processo_id):
        return classificar_pendencia(texto)


class TestClassificadorComLLM:
    @pytest.fixture
    def llm(self, monkeypatch):
        monkeypatch.setattr("app.core.llm.disponivel", lambda papel: True)

    def _fingir(self, monkeypatch, resposta=None, erro=None):
        def falso(papel, sistema, usuario, esquema):
            assert papel == "pendencia"
            assert "unifilar_inconsistente" in usuario  # categorias vêm de CATEGORIAS
            if erro:
                raise erro
            return esquema(**resposta)

        monkeypatch.setattr("app.core.llm.completar_json", falso)

    def test_llm_valido_e_usado(self, llm, monkeypatch):
        from app.tracing import listar_passos_detalhados

        self._fingir(
            monkeypatch, {"categoria": "art_irregular", "justificativa": "cita a ART"}
        )
        # texto que a linha de base classificaria diferente
        cat, corr = _rodar("Procuração ausente.", "p-llm")
        assert cat == "art_irregular"
        assert corr == CATEGORIAS["art_irregular"]["correcao"]
        passo = listar_passos_detalhados("p-llm")[0]
        assert "pelo LLM" in passo.passo.decisao
        assert len(passo.prompts) == 1
        assert passo.prompts[0].startswith("classificar_pendencia@v1#")

    def test_categoria_desconhecida_cai_na_linha_de_base(self, llm, monkeypatch):
        from app.tracing import listar_passos_detalhados

        self._fingir(monkeypatch, {"categoria": "inventada", "justificativa": "?"})
        cat, _ = _rodar("Procuração ausente.", "p-inv")
        assert cat == "documentacao_incompleta"
        assert "LLM falhou" in listar_passos_detalhados("p-inv")[0].passo.decisao

    def test_erro_do_llm_cai_na_linha_de_base(self, llm, monkeypatch):
        from app.core.llm import LLMErro
        from app.tracing import listar_passos_detalhados

        self._fingir(monkeypatch, erro=LLMErro("boom"))
        cat, _ = _rodar("Procuração ausente.", "p-err")
        assert cat == "documentacao_incompleta"
        assert "LLM falhou" in listar_passos_detalhados("p-err")[0].passo.decisao

    def test_sem_llm_nao_registra_prompt(self):
        from app.tracing import listar_passos_detalhados

        _rodar("Procuração ausente.", "p-sem")
        passo = listar_passos_detalhados("p-sem")[0]
        assert passo.prompts == []
        assert "palavras-chave" in passo.passo.decisao
