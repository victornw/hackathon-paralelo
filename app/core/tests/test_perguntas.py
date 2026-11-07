import inspect
from datetime import datetime

import pytest

from app.core.perguntas import EXIGENCIAS, perguntas_pendentes
from app.portal_sim import portal
from app.schemas import CampoExtraido, Carga, Pergunta
from app.tracing import listar_passos

CAMPOS_DO_PORTAL = {"telefone", "qtd_ucs_credito", "modalidade_compensacao"}


def por_campo(perguntas):
    return {p.campo: p for p in perguntas}


def respondida(campo: str, resposta: str = "ok") -> Pergunta:
    return Pergunta(
        id=campo,
        campo=campo,
        texto="?",
        resposta=resposta,
        respondida_em=datetime(2026, 11, 9),
    )


@pytest.fixture
def completo(confirmado):
    """Processo sem nenhuma pendência de dado; só faltam as respostas do portal."""
    confirmado.visita.relacao_cargas = [Carga(descricao="chuveiro", potencia_w=5500)]
    return confirmado


def test_processo_do_exemplo_pede_cargas_cabo_e_confirmacao_das_strings(processo):
    campos = por_campo(perguntas_pendentes(processo))
    assert {"relacao_cargas", "bitola_ca_mm2", "strings"} <= campos.keys()
    assert campos["strings"].destinatario == "engenheiro"
    assert campos["relacao_cargas"].destinatario == "integrador"


def test_id_da_pergunta_e_o_campo(processo):
    assert all(p.id == p.campo for p in perguntas_pendentes(processo))


def test_ids_sao_unicos(protocolado):
    ids = [p.id for p in perguntas_pendentes(protocolado)]
    assert len(ids) == len(set(ids))


def test_chamar_de_novo_devolve_as_mesmas_perguntas(processo):
    primeira = perguntas_pendentes(processo)
    processo.perguntas = primeira
    assert perguntas_pendentes(processo) == primeira


def test_pergunta_respondida_nao_volta(processo):
    processo.perguntas = [respondida("relacao_cargas", "chuveiro 5500 W")]
    assert "relacao_cargas" not in por_campo(perguntas_pendentes(processo))


def test_pergunta_sem_resposta_continua_pendente(processo):
    processo.perguntas = [
        Pergunta(id="relacao_cargas", campo="relacao_cargas", texto="?")
    ]
    assert "relacao_cargas" in por_campo(perguntas_pendentes(processo))


def test_dado_que_chegou_tira_a_pergunta(processo):
    processo.visita.relacao_cargas = [Carga(descricao="chuveiro", potencia_w=5500)]
    assert "relacao_cargas" not in por_campo(perguntas_pendentes(processo))


def test_nao_altera_o_processo(processo):
    antes = processo.model_dump_json()
    perguntas_pendentes(processo)
    assert processo.model_dump_json() == antes


class TestBitola:
    def test_texto_traz_a_sugestao_da_tabela_quando_o_disjuntor_e_conhecido(
        self, processo
    ):
        texto = por_campo(perguntas_pendentes(processo))["bitola_ca_mm2"].texto
        assert "25 A" in texto and "4 mm²" in texto
        assert "a validar" in texto

    def test_sem_disjuntor_a_pergunta_nao_sugere_nada(self, processo):
        processo.visita.disjuntor_ca_a = None
        texto = por_campo(perguntas_pendentes(processo))["bitola_ca_mm2"].texto
        assert "mm²" in texto and "tabela" not in texto

    def test_sugestao_nunca_e_gravada_na_visita(self, processo):
        perguntas_pendentes(processo)
        assert processo.visita.bitola_ca_mm2 is None

    def test_bitola_informada_remove_a_pergunta(self, processo):
        processo.visita.bitola_ca_mm2 = 6
        assert "bitola_ca_mm2" not in por_campo(perguntas_pendentes(processo))


class TestCamposDaConta:
    def test_campo_de_baixa_confianca_pede_confirmacao_do_valor_lido(self, processo):
        processo.campos["titular"] = CampoExtraido(valor="MARIA S1LVA", confianca=0.5)
        pergunta = por_campo(perguntas_pendentes(processo))["campos.titular"]
        assert "MARIA S1LVA" in pergunta.texto
        assert "Está correto" in pergunta.texto

    def test_campo_ilegivel_pede_o_valor(self, processo):
        processo.campos["cpf_cnpj"] = CampoExtraido(valor=None, confianca=0.1)
        pergunta = por_campo(perguntas_pendentes(processo))["campos.cpf_cnpj"]
        assert "Não consegui ler" in pergunta.texto

    def test_campo_ausente_da_extracao_pede_o_valor(self, processo):
        del processo.campos["cidade"]
        assert "campos.cidade" in por_campo(perguntas_pendentes(processo))

    def test_campo_confiavel_nao_gera_pergunta(self, processo):
        assert not [
            p for p in perguntas_pendentes(processo) if p.campo.startswith("campos.")
        ]

    def test_campo_que_nenhum_documento_usa_nao_gera_pergunta(self, processo):
        assert processo.campos["consumo_medio_kwh"].incerto
        assert "campos.consumo_medio_kwh" not in por_campo(
            perguntas_pendentes(processo)
        )

    def test_unidade_aparece_no_valor_lido(self, processo):
        processo.campos["tensao_atendimento_v"] = CampoExtraido(
            valor=220, confianca=0.4
        )
        assert (
            '"220 V"'
            in por_campo(perguntas_pendentes(processo))[
                "campos.tensao_atendimento_v"
            ].texto
        )


class TestVisitaEKit:
    def test_disjuntor_do_padrao_com_confianca_baixa_pede_confirmacao(self, processo):
        processo.visita.disjuntor_padrao_a = CampoExtraido(valor=50, confianca=0.4)
        texto = por_campo(perguntas_pendentes(processo))["disjuntor_padrao_a"].texto
        assert '"50 A"' in texto

    def test_disjuntor_do_padrao_ausente_pede_o_valor(self, processo):
        processo.visita.disjuntor_padrao_a = None
        assert "disjuntor_padrao_a" in por_campo(perguntas_pendentes(processo))

    @pytest.mark.parametrize(
        "campo, limpar",
        [
            (
                "distancia_inversor_quadro_m",
                lambda p: setattr(p.visita, "distancia_inversor_quadro_m", None),
            ),
            ("coordenadas_padrao", lambda p: setattr(p.visita, "latitude", None)),
            ("coordenadas_padrao", lambda p: setattr(p.visita, "longitude", None)),
            ("tipo_ramal", lambda p: setattr(p.visita, "tipo_ramal", None)),
            ("email_contato", lambda p: setattr(p, "email_contato", None)),
            (
                "coef_temp_voc_pct_c",
                lambda p: setattr(p.kit.modulo, "coef_temp_voc_pct_c", None),
            ),
            (
                "certificado_inmetro",
                lambda p: setattr(p.kit.inversor, "certificado_inmetro", None),
            ),
        ],
    )
    def test_dado_faltando_gera_a_pergunta(self, completo, campo, limpar):
        assert campo not in por_campo(perguntas_pendentes(completo))
        limpar(completo)
        assert campo in por_campo(perguntas_pendentes(completo))

    def test_texto_do_coeficiente_cita_o_modulo(self, completo):
        completo.kit.modulo.coef_temp_voc_pct_c = None
        texto = por_campo(perguntas_pendentes(completo))["coef_temp_voc_pct_c"].texto
        assert completo.kit.modulo.modelo in texto

    def test_strings_sugeridas_pedem_confirmacao_do_engenheiro_com_a_proposta(
        self, processo
    ):
        pergunta = por_campo(perguntas_pendentes(processo))["strings"]
        assert pergunta.destinatario == "engenheiro"
        assert (
            "MPPT 1: 5 módulos" in pergunta.texto
            and "MPPT 2: 5 módulos" in pergunta.texto
        )

    def test_strings_confirmadas_nao_geram_pergunta(self, completo):
        assert "strings" not in por_campo(perguntas_pendentes(completo))

    def test_sem_strings_o_integrador_e_quem_informa(self, completo):
        completo.kit.strings = []
        pergunta = por_campo(perguntas_pendentes(completo))["strings"]
        assert pergunta.destinatario == "integrador"

    def test_sem_kit_nao_pergunta_do_kit(self, processo):
        processo.kit = None
        campos = por_campo(perguntas_pendentes(processo))
        assert (
            not {"coef_temp_voc_pct_c", "certificado_inmetro", "strings"}
            & campos.keys()
        )


class TestPortal:
    def test_pede_os_campos_do_formulario_que_o_processo_nao_tem(self, completo):
        assert set(por_campo(perguntas_pendentes(completo))) == CAMPOS_DO_PORTAL

    def test_resposta_chega_na_chave_que_o_portal_le(self, completo):
        completo.perguntas = [respondida("telefone", "85999990000")]
        assert set(por_campo(perguntas_pendentes(completo))) == CAMPOS_DO_PORTAL - {
            "telefone"
        }

    def test_com_tudo_respondido_nao_sobra_nada(self, completo):
        completo.perguntas = [respondida(c) for c in CAMPOS_DO_PORTAL]
        assert perguntas_pendentes(completo) == []

    def test_chaves_batem_com_as_que_o_portal_le(self):
        fonte = inspect.getsource(portal)
        assert all(f'_resposta(processo, "{c}")' in fonte for c in CAMPOS_DO_PORTAL)


def test_todo_texto_e_uma_pergunta(protocolado):
    for p in perguntas_pendentes(protocolado):
        assert "?" in p.texto, p.campo


def test_perguntas_geradas_sao_as_exigencias_que_faltam(processo):
    processo.campos = {}
    processo.email_contato = None
    processo.kit.modulo.coef_temp_voc_pct_c = None
    processo.kit.inversor.certificado_inmetro = None
    processo.visita = processo.visita.model_copy(update={"disjuntor_padrao_a": None})
    gerados = {p.campo for p in perguntas_pendentes(processo)}
    esperados = {e.campo for e in EXIGENCIAS if e.falta(processo)}
    assert gerados == esperados


def test_registra_passo_de_trace(processo):
    perguntas_pendentes(processo)
    (passo,) = listar_passos(processo.id)
    assert passo.passo == "perguntas_pendentes"
    assert passo.erro is None
