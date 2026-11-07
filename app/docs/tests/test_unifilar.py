from pathlib import Path
from xml.etree import ElementTree

import pytest

from app.docs.unifilar import A_INFORMAR, SUFIXO_SUGERIDA, gerar_unifilar
from app.schemas import CampoExtraido, Processo, StringFV

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "processo_exemplo.json"


@pytest.fixture
def processo() -> Processo:
    return Processo.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def _svg(processo: Processo, pasta: Path) -> str:
    svg_path, _ = gerar_unifilar(processo, pasta)
    return svg_path.read_text(encoding="utf-8")


def test_2mppt_gera_svg_e_pdf(processo, tmp_path):
    pasta = tmp_path / "saida"
    svg_path, pdf_path = gerar_unifilar(processo, pasta)

    assert svg_path == pasta / "unifilar_proc-exemplo-001.svg"
    assert pdf_path == pasta / "unifilar_proc-exemplo-001.pdf"
    assert pdf_path.read_bytes().startswith(b"%PDF")
    assert pdf_path.stat().st_size > 2000

    svg = svg_path.read_text(encoding="utf-8")
    ElementTree.fromstring(svg.encode("utf-8"))  # XML bem formado
    assert "{{" not in svg
    assert "Template 2 MPPTs" in svg
    assert "MARIA SINTETICA DA SILVA" in svg
    assert "7000123456" in svg
    assert "MPPT 1" in svg and "MPPT 2" in svg
    assert "STRING 2" in svg
    assert SUFIXO_SUGERIDA in svg
    assert "5 módulos em série × 550 Wp" in svg
    assert "10 × 550 Wp = 5,5 kWp" in svg
    assert "5.000 W" in svg
    assert "25 A" in svg and "50 A" in svg
    assert "Comprimento: 8 m" in svg


def test_bitola_ausente_vira_a_informar(processo, tmp_path):
    svg = _svg(processo, tmp_path)
    assert (
        f'Seção: <tspan fill="#c62828" font-weight="bold">{A_INFORMAR}</tspan>' in svg
    )
    assert "mm²" not in svg


def test_bitola_informada_formato_brasileiro(processo, tmp_path):
    processo.visita.bitola_ca_mm2 = 2.5
    svg = _svg(processo, tmp_path)
    assert "Seção: 2,5 mm²" in svg


def test_campo_com_valor_none_vira_a_informar(processo, tmp_path):
    processo.campos["titular"] = CampoExtraido(valor=None, confianca=0.2)
    del processo.campos["uc"]
    processo.visita.disjuntor_padrao_a = None
    svg = _svg(processo, tmp_path)
    assert "MARIA SINTETICA" not in svg
    assert svg.count(A_INFORMAR) >= 4  # titular, uc, disjuntor geral, bitola


def test_1mppt_usa_template_de_uma_string(processo, tmp_path):
    processo.kit.strings = [StringFV(mppt=1, modulos_em_serie=10)]
    svg = _svg(processo, tmp_path)
    assert "Template 1 MPPT" in svg
    assert "STRING 2" not in svg
    assert "MPPT 2" not in svg
    assert "10 módulos em série × 550 Wp" in svg
    assert SUFIXO_SUGERIDA not in svg


def test_sem_strings_usa_num_mppt_do_inversor(processo, tmp_path):
    processo.kit.strings = []
    processo.kit.inversor.num_mppt = 1
    svg = _svg(processo, tmp_path)
    assert "Template 1 MPPT" in svg
    assert A_INFORMAR in svg


def test_valores_escapados(processo, tmp_path):
    processo.campos["titular"] = CampoExtraido(
        valor="JOÃO & FILHOS <LTDA>", confianca=0.99
    )
    svg_path, pdf_path = gerar_unifilar(processo, tmp_path)
    svg = svg_path.read_text(encoding="utf-8")
    assert "JOÃO &amp; FILHOS &lt;LTDA&gt;" in svg
    ElementTree.fromstring(svg.encode("utf-8"))
    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_microinversor_fora_do_escopo(processo, tmp_path):
    processo.kit.inversor.microinversor = True
    with pytest.raises(ValueError, match="microinversor"):
        gerar_unifilar(processo, tmp_path)


def test_kit_ausente(processo, tmp_path):
    processo.kit = None
    with pytest.raises(ValueError, match="kit"):
        gerar_unifilar(processo, tmp_path)


def test_mais_de_2_mppts(processo, tmp_path):
    processo.kit.strings.append(StringFV(mppt=3, modulos_em_serie=5))
    with pytest.raises(ValueError, match="3 MPPTs"):
        gerar_unifilar(processo, tmp_path)


def test_selo_de_simulacao(processo, tmp_path):
    assert "SIMULAÇÃO — DADOS SINTÉTICOS" in _svg(processo, tmp_path / "a")
    processo.simulacao = False
    assert "SIMULAÇÃO" not in _svg(processo, tmp_path / "b")
