from pypdf import PdfReader

from app.docs.anexo_a import carga_instalada_kw, gerar_anexo_a, potencia_instalada_kw
from app.docs.memorial import gerar_memorial
from app.docs.pdf_base import latin1, num
from app.schemas import Carga


def texto(caminho) -> str:
    return "\n".join(p.extract_text() for p in PdfReader(caminho).pages)


def test_num_formato_brasileiro():
    assert num(5500) == "5.500"
    assert num(5.5) == "5,5"
    assert num(22.7) == "22,7"
    assert num(5.5, 2) == "5,50"
    assert num(None) == "A INFORMAR"


def test_latin1_troca_caracteres_fora_da_fonte():
    assert latin1("a — b ≤ c") == "a - b <= c"
    assert latin1("mm² × °C ç") == "mm² × °C ç"


def test_potencia_instalada_e_o_menor_entre_modulos_e_inversor(processo):
    assert (
        potencia_instalada_kw(processo.kit) == 5.0
    )  # 5,5 kWp de módulos, inversor 5 kW
    processo.kit.qtd_modulos = 8  # 4,4 kWp
    assert potencia_instalada_kw(processo.kit) == 4.4


def test_carga_instalada(processo):
    assert carga_instalada_kw(processo) is None
    processo.visita.relacao_cargas = [
        Carga(descricao="Ar-condicionado 12.000 BTU", potencia_w=1100, quantidade=2),
        Carga(descricao="Geladeira", potencia_w=250),
    ]
    assert carga_instalada_kw(processo) == 2.45


def test_anexo_a_preenche_e_marca_o_que_falta(processo, tmp_path):
    t = texto(gerar_anexo_a(processo, tmp_path))
    assert "7000123456" in t
    assert "MARIA SINTETICA DA SILVA" in t
    assert "INV-5K-2MPPT" in t
    assert "10 x 550 Wp = 5,50 kWp" in t
    assert "5,00 kW" in t
    assert "SIMULAÇÃO" in t
    # relação de cargas e modalidade não vieram: nada é presumido
    assert t.count("A INFORMAR") >= 2


def test_anexo_a_com_relacao_de_cargas(processo, tmp_path):
    processo.visita.relacao_cargas = [Carga(descricao="Chuveiro", potencia_w=5500)]
    t = texto(gerar_anexo_a(processo, tmp_path))
    assert "Chuveiro" in t and "5,50 kW" in t


def test_memorial_descreve_arranjo_e_protecoes(processo, tmp_path):
    t = texto(gerar_memorial(processo, tmp_path))
    assert "MPPT 1: 5 módulos em série" in t
    assert "a confirmar pelo engenheiro" in t  # strings sugeridas
    assert "249,5 V" in t
    assert "25 A" in t  # disjuntor CA
    assert "7.6.1.5" in t and "7.6.1.6" in t
    # bitola ausente na fixture
    assert "Cabo CA inversor-quadro" in t and "A INFORMAR" in t


def test_sem_kit_falha_com_mensagem(processo, tmp_path):
    processo.kit = None
    for gerar in (gerar_anexo_a, gerar_memorial):
        try:
            gerar(processo, tmp_path)
        except ValueError as e:
            assert "Kit ausente" in str(e)
        else:
            raise AssertionError("deveria falhar sem kit")


def test_anexo_a_imprime_a_modalidade_respondida(processo, tmp_path):
    from app.schemas import Pergunta

    processo.perguntas.append(
        Pergunta(
            id="modalidade_compensacao",
            campo="modalidade_compensacao",
            texto="?",
            resposta="Autoconsumo local",
        )
    )
    t = texto(gerar_anexo_a(processo, tmp_path))
    assert "Autoconsumo local" in t
