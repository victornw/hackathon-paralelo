"""Testes da extração com LLM falso, sobre os PDFs sintéticos de fixtures/contas."""

import json
from pathlib import Path

import pytest
from fpdf import FPDF
from PIL import Image

from app.core import extracao
from app.core.extracao import KitIncompleto, extrair_conta, extrair_kit, extrair_padrao
from app.core.llm import LLMErro
from app.schemas import DadosVisita
from app.tracing import listar_passos, processo_atual

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "contas"
CLIENTES = [1, 2, 3]
FILLER = (
    "Texto de enchimento para passar do limite mínimo de caracteres da camada de texto. "
    * 3
)


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.setenv("RELOGIO_INICIO", "2026-11-13")


class LLMFalso:
    def __init__(self, monkeypatch, resposta=None, visao=False):
        self.resposta = resposta
        self.chamadas: list[tuple] = []
        monkeypatch.setattr(extracao, "completar_json", self.completar_json)
        monkeypatch.setattr(
            extracao, "disponivel", lambda papel: visao or papel != "visao"
        )

    def completar_json(self, papel, sistema, usuario, esquema, imagens=()):
        self.chamadas.append((papel, usuario, list(imagens)))
        if isinstance(self.resposta, Exception):
            raise self.resposta
        return esquema.model_validate(self.resposta)


def gabarito(n: int) -> dict:
    return json.loads(
        (FIXTURES / f"cliente_{n}_gabarito.json").read_text(encoding="utf-8")
    )


def resposta_conta(n: int, confianca: float = 0.97) -> dict:
    return {
        chave: {"valor": c["valor"], "confianca": confianca, "trecho": c["trecho"]}
        for chave, c in gabarito(n)["campos"].items()
    }


def resposta_kit(n: int) -> dict:
    kit = gabarito(n)["kit"]
    return {
        "fabricante_modulo": "qualquer",
        "modelo_modulo": kit["modelo_modulo"],
        "qtd_modulos": kit["qtd_modulos"],
        "fabricante_inversor": "qualquer",
        "modelo_inversor": kit["modelo_inversor"],
        "strings": kit["strings"],
    }


def criar_pdf(caminho: Path, linhas: list[str], imagem: Path | None = None) -> Path:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    for linha in linhas:
        pdf.cell(0, 6, linha, new_x="LMARGIN", new_y="NEXT")
    if imagem:
        pdf.image(str(imagem), w=50)
    pdf.output(str(caminho))
    return caminho


def criar_png(caminho: Path) -> Path:
    Image.new("RGB", (40, 40), "white").save(caminho)
    return caminho


# ---------------------------------------------------------------------------
# extrair_conta
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n", CLIENTES)
def test_conta_sintetica_vira_campos_com_confianca_no_teto(monkeypatch, n):
    LLMFalso(monkeypatch, resposta_conta(n))
    campos = extrair_conta(FIXTURES / f"cliente_{n}_conta.pdf")
    esperado = gabarito(n)["campos"]
    assert set(campos) == set(esperado)
    for chave, c in esperado.items():
        campo = campos[chave]
        assert campo.valor == c["valor"], chave
        assert campo.confianca == 0.95, chave
        assert campo.fonte.documento == f"cliente_{n}_conta.pdf"
        assert campo.fonte.pagina == 1
        assert campo.fonte.trecho == c["trecho"]
        assert not campo.incerto


def test_trecho_inventado_limita_a_confianca_a_0_5(monkeypatch):
    resposta = resposta_conta(1)
    resposta["uc"]["trecho"] = "Código da UC: 99999999"
    resposta["uc"]["valor"] = "99999999"
    LLMFalso(monkeypatch, resposta)
    campos = extrair_conta(FIXTURES / "cliente_1_conta.pdf")
    assert campos["uc"].confianca <= 0.5
    assert campos["uc"].incerto
    assert campos["titular"].confianca == 0.95


def test_valor_que_nao_sai_do_trecho_limita_a_0_5(monkeypatch):
    resposta = resposta_conta(1)
    resposta["uc"]["valor"] = "87654321"
    LLMFalso(monkeypatch, resposta)
    campo = extrair_conta(FIXTURES / "cliente_1_conta.pdf")["uc"]
    assert campo.valor == "87654321"
    assert campo.confianca <= 0.5


def test_campo_sem_trecho_limita_a_0_5(monkeypatch):
    resposta = resposta_conta(1)
    resposta["cidade"]["trecho"] = None
    LLMFalso(monkeypatch, resposta)
    assert extrair_conta(FIXTURES / "cliente_1_conta.pdf")["cidade"].confianca <= 0.5


def test_campo_ilegivel_volta_none_e_confianca_zero(monkeypatch):
    resposta = resposta_conta(1)
    resposta["cpf_cnpj"] = {"valor": None, "confianca": 0.9, "trecho": None}
    del resposta["classe"]
    LLMFalso(monkeypatch, resposta)
    campos = extrair_conta(FIXTURES / "cliente_1_conta.pdf")
    for chave in ("cpf_cnpj", "classe"):
        assert campos[chave].valor is None
        assert campos[chave].confianca == 0
        assert campos[chave].incerto


@pytest.mark.parametrize(
    ("chave", "linha", "valor", "esperado"),
    [
        ("tensao_atendimento_v", "Tensão de atendimento: 230 V", 230, 0.3),
        ("tensao_atendimento_v", "Tensão de atendimento: 220 V", "220 V", 0.95),
        ("uc", "Código da UC: 123", "123", 0.3),
        ("uc", "Código da UC: 0/1234567-8", "0/1234567-8", 0.95),
        ("subgrupo", "Subgrupo: Z9", "Z9", 0.3),
        ("subgrupo", "Subgrupo: b 1", "b 1", 0.95),
        ("cpf_cnpj", "CPF: 12.345", "12.345", 0.3),
        ("cpf_cnpj", "CNPJ: 12.345.678/0001-95", "12.345.678/0001-95", 0.95),
        ("cpf_cnpj", "CPF: ***.456.789-**", "***.456.789-**", 0.95),
        ("consumo_medio_kwh", "Consumo médio: 0 kWh", 0, 0.3),
        ("consumo_medio_kwh", "Consumo médio: 1.250,5 kWh", "1.250,5", 0.95),
        ("tipo_ligacao", "Ligação: TRIFÁSICA", "trifásica", 0.95),
        ("tipo_ligacao", "Ligação: monofásico", "Monofásico", 0.95),
        ("tipo_ligacao", "Ligação: tipo especial", "tipo especial", 0.3),
    ],
)
def test_formato_e_faixa_derrubam_a_confianca(
    monkeypatch, tmp_path, chave, linha, valor, esperado
):
    pdf = criar_pdf(tmp_path / "conta.pdf", [FILLER, linha])
    LLMFalso(monkeypatch, {chave: {"valor": valor, "confianca": 0.99, "trecho": linha}})
    campo = extrair_conta(pdf)[chave]
    assert campo.confianca == esperado


def test_tipo_ligacao_e_normalizado(monkeypatch, tmp_path):
    pdf = criar_pdf(tmp_path / "conta.pdf", [FILLER, "Ligação: BIFÁSICA"])
    LLMFalso(
        monkeypatch,
        {
            "tipo_ligacao": {
                "valor": "Bifásica",
                "confianca": 0.9,
                "trecho": "Ligação: BIFÁSICA",
            }
        },
    )
    assert extrair_conta(pdf)["tipo_ligacao"].valor == "bifasico"


def test_pdf_escaneado_sem_visao_devolve_tudo_vazio_sem_chamar_llm(
    monkeypatch, tmp_path
):
    imagem = criar_png(tmp_path / "scan.png")
    pdf = criar_pdf(tmp_path / "conta_escaneada.pdf", [], imagem=imagem)
    falso = LLMFalso(monkeypatch, {}, visao=False)
    campos = extrair_conta(pdf)
    assert set(campos) == set(extracao.CHAVES_CONTA)
    for campo in campos.values():
        assert campo.valor is None
        assert campo.confianca == 0
        assert "sem camada de texto e sem modelo de visão" in campo.fonte.trecho
        assert campo.fonte.documento == "conta_escaneada.pdf"
    assert falso.chamadas == []


def test_imagem_sem_visao_devolve_tudo_vazio(monkeypatch, tmp_path):
    falso = LLMFalso(monkeypatch, {}, visao=False)
    campos = extrair_conta(criar_png(tmp_path / "foto_conta.png"))
    assert all(c.valor is None and c.confianca == 0 for c in campos.values())
    assert falso.chamadas == []


def test_imagem_com_visao_tem_teto_de_0_8(monkeypatch, tmp_path):
    falso = LLMFalso(monkeypatch, resposta_conta(1), visao=True)
    campos = extrair_conta(criar_png(tmp_path / "foto_conta.png"))
    assert falso.chamadas[0][0] == "visao"
    assert len(falso.chamadas[0][2]) == 1
    assert {c.confianca for c in campos.values()} == {0.8}


def test_pdf_escaneado_com_visao_envia_as_imagens_do_pdf(monkeypatch, tmp_path):
    pdf = criar_pdf(tmp_path / "scan.pdf", [], imagem=criar_png(tmp_path / "p.png"))
    falso = LLMFalso(monkeypatch, resposta_conta(2), visao=True)
    campos = extrair_conta(pdf)
    assert falso.chamadas[0][0] == "visao"
    assert falso.chamadas[0][2]
    assert max(c.confianca for c in campos.values()) == 0.8


def test_pdf_sem_texto_e_sem_imagem_devolve_vazio(monkeypatch, tmp_path):
    falso = LLMFalso(monkeypatch, {}, visao=True)
    campos = extrair_conta(criar_pdf(tmp_path / "branco.pdf", []))
    assert all(c.valor is None for c in campos.values())
    assert falso.chamadas == []


def test_formato_nao_suportado(monkeypatch, tmp_path):
    LLMFalso(monkeypatch, {})
    with pytest.raises(ValueError):
        extrair_conta(tmp_path / "conta.docx")


def test_passo_gravado_no_trace_com_decisao(monkeypatch):
    LLMFalso(monkeypatch, resposta_conta(1))
    with processo_atual("proc-conta"):
        extrair_conta(FIXTURES / "cliente_1_conta.pdf")
    (passo,) = listar_passos("proc-conta")
    assert passo.passo == "extrair_conta"
    assert "10 de 10" in passo.decisao
    assert passo.erro is None


def test_falha_do_llm_propaga_e_fica_no_trace(monkeypatch):
    LLMFalso(monkeypatch, LLMErro("fora do esquema"))
    with processo_atual("proc-erro"), pytest.raises(LLMErro):
        extrair_conta(FIXTURES / "cliente_1_conta.pdf")
    assert "LLMErro" in listar_passos("proc-erro")[0].erro


# ---------------------------------------------------------------------------
# extrair_kit
# ---------------------------------------------------------------------------


def test_catalogo_e_coerente():
    catalogo = extracao._catalogo()
    modulos = [extracao.Modulo(**m) for m in catalogo["modulos"]]
    inversores = [extracao.Inversor(**i) for i in catalogo["inversores"]]
    assert 3 <= len(modulos) <= 4 and all(550 <= m.potencia_wp <= 610 for m in modulos)
    assert 3 <= len(inversores) <= 4 and all(
        3000 <= i.potencia_nominal_w <= 8000 or i.microinversor for i in inversores
    )
    assert any(i.num_mppt == 2 and not i.microinversor for i in inversores)
    assert any(i.microinversor for i in inversores)
    assert any(i.certificado_inmetro is None for i in inversores)
    assert sum(i.certificado_inmetro is not None for i in inversores) >= 2


@pytest.mark.parametrize("n", CLIENTES)
def test_kit_preenche_especificacoes_pelo_catalogo(monkeypatch, n):
    falso = LLMFalso(monkeypatch, resposta_kit(n))
    kit = extrair_kit([FIXTURES / f"cliente_{n}_proposta.pdf"])
    esperado = gabarito(n)["kit"]
    assert kit.modulo.modelo == esperado["modelo_modulo"]
    assert kit.inversor.modelo == esperado["modelo_inversor"]
    assert kit.qtd_modulos == esperado["qtd_modulos"]
    assert kit.modulo.voc_v > 0 and kit.modulo.isc_a > 0
    assert kit.inversor.corrente_max_saida_a > 0
    assert [(s.mppt, s.modulos_em_serie) for s in kit.strings] == [
        (s["mppt"], s["modulos_em_serie"]) for s in esperado["strings"]
    ]
    assert all(not s.sugerida for s in kit.strings)
    assert falso.chamadas[0][0] == "extracao"


def test_kit_do_catalogo_mantem_inmetro_e_micro(monkeypatch):
    LLMFalso(monkeypatch, resposta_kit(2))
    micro = extrair_kit([FIXTURES / "cliente_2_proposta.pdf"]).inversor
    assert micro.microinversor and micro.certificado_inmetro

    LLMFalso(monkeypatch, resposta_kit(3))
    sem_certificado = extrair_kit([FIXTURES / "cliente_3_proposta.pdf"]).inversor
    assert sem_certificado.certificado_inmetro is None


def test_kit_com_datasheet_fora_do_catalogo(monkeypatch, tmp_path):
    proposta = criar_pdf(
        tmp_path / "proposta.pdf",
        [FILLER, "12 x Zeta Solar ZS-700X 700 Wp", "1 x Omega Inversor OI-6K 6 kW"],
    )
    datasheet = criar_pdf(
        tmp_path / "datasheet.pdf",
        [
            "Datasheet ZS-700X Voc 55,1 V Isc 16,0 A",
            "Datasheet OI-6K Pmax CC 9000 W Vmax CC 600 V Iout 27,3 A",
        ],
    )
    LLMFalso(
        monkeypatch,
        {
            "fabricante_modulo": "Zeta Solar",
            "modelo_modulo": "ZS-700X",
            "qtd_modulos": 12,
            "fabricante_inversor": "Omega Inversor",
            "modelo_inversor": "OI-6K",
            "especificacoes_modulo": {"potencia_wp": 700, "voc_v": 55.1, "isc_a": 16.0},
            "especificacoes_inversor": {
                "potencia_nominal_w": 6000,
                "potencia_max_cc_w": 9000,
                "tensao_max_cc_v": 600,
                "corrente_max_saida_a": 27.3,
            },
        },
    )
    kit = extrair_kit([proposta, datasheet])
    assert kit.modulo.voc_v == 55.1
    assert kit.inversor.potencia_max_cc_w == 9000
    assert kit.inversor.num_mppt == 1
    assert kit.potencia_total_wp == 8400


def test_kit_fora_do_catalogo_sem_datasheet_levanta_kit_incompleto(
    monkeypatch, tmp_path
):
    proposta = criar_pdf(
        tmp_path / "proposta.pdf",
        [FILLER, "12 x Zeta Solar ZS-700X", "1 x Omega OI-6K"],
    )
    LLMFalso(
        monkeypatch,
        {
            "fabricante_modulo": "Zeta Solar",
            "modelo_modulo": "ZS-700X",
            "qtd_modulos": 12,
            "fabricante_inversor": "Omega",
            "modelo_inversor": "OI-6K",
        },
    )
    with pytest.raises(KitIncompleto) as erro:
        extrair_kit([proposta])
    assert set(erro.value.faltando) == {
        "modulo.potencia_wp",
        "modulo.voc_v",
        "modulo.isc_a",
        "inversor.potencia_nominal_w",
        "inversor.potencia_max_cc_w",
        "inversor.tensao_max_cc_v",
        "inversor.corrente_max_saida_a",
    }


def test_modelo_que_nao_esta_no_documento_e_descartado(monkeypatch):
    resposta = resposta_kit(1)
    resposta["modelo_modulo"] = "HS-580M"
    LLMFalso(monkeypatch, resposta)
    with pytest.raises(KitIncompleto) as erro:
        extrair_kit([FIXTURES / "cliente_1_proposta.pdf"])
    assert "modulo.modelo" in erro.value.faltando


def test_quantidade_ausente_levanta_kit_incompleto(monkeypatch):
    resposta = resposta_kit(1)
    resposta["qtd_modulos"] = None
    LLMFalso(monkeypatch, resposta)
    with pytest.raises(KitIncompleto) as erro:
        extrair_kit([FIXTURES / "cliente_1_proposta.pdf"])
    assert erro.value.faltando == ["qtd_modulos"]


def test_pdf_sem_texto_levanta_kit_incompleto_sem_chamar_llm(monkeypatch, tmp_path):
    falso = LLMFalso(monkeypatch, resposta_kit(1))
    with pytest.raises(KitIncompleto):
        extrair_kit([criar_pdf(tmp_path / "branco.pdf", [])])
    assert falso.chamadas == []


# ---------------------------------------------------------------------------
# extrair_padrao
# ---------------------------------------------------------------------------


def resposta_padrao(disjuntor=40, polos=2, trecho="Disjuntor bipolar C40"):
    return {
        "disjuntor_padrao_a": {"valor": disjuntor, "confianca": 0.95, "trecho": trecho},
        "polos_padrao": {"valor": polos, "confianca": 0.95, "trecho": trecho},
    }


def test_padrao_sem_visao_devolve_visita_vazia(monkeypatch, tmp_path):
    falso = LLMFalso(monkeypatch, resposta_padrao(), visao=False)
    visita = extrair_padrao(criar_png(tmp_path / "padrao.png"))
    assert visita == DadosVisita()
    assert falso.chamadas == []


def test_padrao_com_visao_tem_teto_de_0_8(monkeypatch, tmp_path):
    falso = LLMFalso(monkeypatch, resposta_padrao(), visao=True)
    visita = extrair_padrao(criar_png(tmp_path / "padrao.png"))
    assert falso.chamadas[0][0] == "visao" and falso.chamadas[0][2]
    assert (visita.disjuntor_padrao_a.valor, visita.disjuntor_padrao_a.confianca) == (
        40,
        0.8,
    )
    assert (visita.polos_padrao.valor, visita.polos_padrao.confianca) == (2, 0.8)
    assert visita.disjuntor_padrao_a.fonte.documento == "padrao.png"


@pytest.mark.parametrize(
    ("resposta", "campo", "maximo"),
    [
        (
            resposta_padrao(disjuntor=63, trecho="Disjuntor bipolar C40"),
            "disjuntor_padrao_a",
            0.5,
        ),
        (resposta_padrao(disjuntor=500, trecho="500 A"), "disjuntor_padrao_a", 0.3),
        (resposta_padrao(polos=4, trecho="4 polos"), "polos_padrao", 0.3),
        (resposta_padrao(polos=3, trecho="Disjuntor C40"), "polos_padrao", 0.5),
        (resposta_padrao(trecho=None), "disjuntor_padrao_a", 0.5),
    ],
)
def test_padrao_valores_duvidosos_baixam_a_confianca(
    monkeypatch, tmp_path, resposta, campo, maximo
):
    LLMFalso(monkeypatch, resposta, visao=True)
    visita = extrair_padrao(criar_png(tmp_path / "padrao.png"))
    assert getattr(visita, campo).confianca <= maximo


def test_padrao_ilegivel_volta_none(monkeypatch, tmp_path):
    resposta = resposta_padrao()
    resposta["polos_padrao"] = {"valor": None, "confianca": 0.7, "trecho": None}
    LLMFalso(monkeypatch, resposta, visao=True)
    visita = extrair_padrao(criar_png(tmp_path / "padrao.png"))
    assert visita.polos_padrao.valor is None
    assert visita.polos_padrao.confianca == 0
