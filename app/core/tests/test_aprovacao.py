import pytest

from app.core.aprovacao import bloqueios_regras
from app.core.orquestrador import _ENTRADAS, Estado, Passo
from app.portal_sim.relogio import hoje
from app.schemas import Camada, Etapa, EventoPortal, ResultadoRegra, StatusRegra


@pytest.fixture
def pacote(processo):
    processo.regras = [
        ResultadoRegra(
            regra_id=f"R0{i}",
            descricao="resultado simulado",
            camada=Camada.TECNICA,
            status=StatusRegra.APROVADA,
            mensagem="evidência simulada",
            fonte_norma="teste",
        )
        for i in range(1, 9)
    ]
    for r in processo.regras[5:]:
        r.status = StatusRegra.NAO_VERIFICADA
    return processo


def test_regras_fora_do_mvp_nao_sao_confundidas_com_obrigatorias(pacote):
    assert bloqueios_regras(pacote) == []


@pytest.mark.parametrize("indice", range(5))
@pytest.mark.parametrize(
    "status", [StatusRegra.INCERTA, StatusRegra.REPROVADA, StatusRegra.NAO_VERIFICADA]
)
def test_qualquer_regra_obrigatoria_pendente_bloqueia(pacote, indice, status):
    pacote.regras[indice].status = status
    assert pacote.regras[indice].regra_id in " ".join(bloqueios_regras(pacote))


def test_ausencia_e_duplicacao_nao_podem_mascarar_conferencia(pacote):
    pacote.regras[1] = pacote.regras[0].model_copy()
    erros = " ".join(bloqueios_regras(pacote))
    assert "R02: conferência ausente" in erros
    assert "R01: resultado duplicado" in erros


def test_aprovacao_antiga_com_criterio_a_validar_tambem_bloqueia(pacote):
    pacote.regras[1].a_validar = True
    assert "R02" in " ".join(bloqueios_regras(pacote))


def test_aprovacao_humana_gravada_nao_contorna_guarda_de_protocolo(pacote):
    pacote.etapa = Etapa.EM_REVISAO
    pacote.revisado_por = "Engenheiro"
    pacote.revisado_em = pacote.criado_em
    pacote.regras[4].status = StatusRegra.INCERTA
    assert _ENTRADAS[Passo.protocolar](Estado(pacote, {}, {}, hoje())) is None


def test_reenvio_tambem_bloqueia_incerteza_depois_da_revisao(pacote):
    pacote.etapa = Etapa.PENDENCIA
    pacote.revisado_por = "Engenheiro"
    pacote.numero_solicitacao = "GD-teste"
    pacote.eventos = [
        EventoPortal(
            numero_solicitacao="GD-teste",
            etapa=Etapa.PENDENCIA,
            descricao="corrigir",
            data=hoje(),
            categoria_pendencia="unifilar_inconsistente",
        )
    ]
    pacote.regras[4].status = StatusRegra.INCERTA
    assert _ENTRADAS[Passo.reenviar](Estado(pacote, {}, {}, hoje())) is None
