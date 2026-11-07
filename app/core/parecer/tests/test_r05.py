import json
from datetime import datetime

import pytest

from app.core.parecer import r05_inmetro as r05
from app.schemas import StatusRegra

# Página sintética no formato da consulta do INMETRO (sem dados de contato)
PAGINA = """<html><head><title>x</title></head><body>
<table><tr><td>Status</td></tr><tr><td>{status}</td></tr></table>
<table><tr><th>Data</th><th>Alteração</th><th>Marca</th><th>Modelo</th>
<th>Descrição</th><th>Código de barras</th></tr>
<tr><td>20/08/2024</td><td>Incluido</td><td>MARCA X</td><td>{modelo}</td>
<td>{descricao}</td><td></td></tr>
<tr><td>20/08/2024</td><td>Excluido</td><td>MARCA X</td><td>{modelo}</td>
<td>DESCRIÇÃO ANTIGA 220/240V</td><td></td></tr>
</table></body></html>"""


def _pagina(status="Ativo", modelo="INV-5K", descricao="Inversor monofásico 5 kW"):
    return PAGINA.format(status=status, modelo=modelo, descricao=descricao)


@pytest.fixture
def p(processo, monkeypatch, tmp_path):
    inv = processo.kit.inversor
    inv.fabricante, inv.modelo, inv.certificado_inmetro = (
        "MARCA X",
        "INV-5K",
        "012345/2024",
    )
    monkeypatch.setattr(r05, "CATALOGO", tmp_path / "vazio.json")
    return processo


def _site(monkeypatch, pagina=None, falha=False):
    chamadas = []

    def baixar(url):
        chamadas.append(url)
        if falha:
            raise TimeoutError("site fora do ar")
        return pagina

    monkeypatch.setattr(r05, "_baixar", baixar)
    return chamadas


def _catalogo(tmp_path, monkeypatch, verificado=True):
    arq = tmp_path / "cat.json"
    arq.write_text(
        json.dumps(
            {
                "inversores": [
                    {
                        "fabricante": "Marca X",
                        "modelo": "inv 5k",
                        "registro": "012345/2024",
                        "tensao_v": 220,
                        "url_certificado": "https://exemplo/cert.pdf",
                        "observacao": "220 V conferido",
                        "verificado_por": "Eng. Fulano" if verificado else None,
                        "verificado_em": "07/11/2026" if verificado else None,
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(r05, "CATALOGO", arq)


def test_leitura_da_pagina_ignora_descricao_excluida():
    c = r05.ler_pagina(
        "n", "u", _pagina(descricao="Saída 220 V"), datetime(2026, 11, 16)
    )
    assert c.status == "Ativo"
    assert [m.modelo for m in c.incluidos] == ["INV-5K"]
    assert c.incluidos[0].descricao == "Saída 220 V"


def test_passo1_inmetro_confirma_220v(p, monkeypatch):
    _site(monkeypatch, _pagina(descricao="Inversor monofásico, tensão de saída 220 V"))
    r = r05.avaliar(p)
    assert r.status == StatusRegra.APROVADA
    ev = r.evidencias[0]
    assert ev.fonte == "INMETRO (consulta automática)" and ev.url and ev.consultado_em


def test_passo1_usa_cache(p, monkeypatch):
    chamadas = _site(monkeypatch, _pagina(descricao="220 V"))
    r05.avaliar(p)
    r05.avaliar(p)
    assert len(chamadas) == 1


def test_passo2_catalogo_verificado(p, monkeypatch, tmp_path):
    _site(monkeypatch, _pagina())  # ativo, sem tensão
    _catalogo(tmp_path, monkeypatch)
    r = r05.avaliar(p)
    assert r.status == StatusRegra.APROVADA
    assert "Eng. Fulano" in r.mensagem
    assert r.evidencias[-1].fonte == "catálogo verificado"


def test_passo2_site_fora_do_ar_cai_no_catalogo(p, monkeypatch, tmp_path):
    _site(monkeypatch, falha=True)
    _catalogo(tmp_path, monkeypatch)
    r = r05.avaliar(p)
    assert r.status == StatusRegra.APROVADA
    assert any("indisponível" in a for a in r.alertas)


def test_candidato_sem_verificacao_nao_conta(p, monkeypatch, tmp_path):
    _site(monkeypatch, falha=True)
    _catalogo(tmp_path, monkeypatch, verificado=False)
    assert r05.avaliar(p).status == StatusRegra.INCERTA


def test_passo3_registro_ativo_sem_tensao_engenheiro_confirma(p, monkeypatch):
    _site(monkeypatch, _pagina())
    r = r05.avaliar(p)
    assert r.status == StatusRegra.INCERTA
    assert {e.fonte for e in r.evidencias} == {
        "INMETRO (consulta automática)",
        "datasheet",
    }
    assert r05.bloqueia(r)

    p.regras = [r]
    r05.confirmar(p, "Eng. Beltrano")
    assert p.regras[0].confirmado_por == "Eng. Beltrano" and p.regras[0].confirmado_em
    assert not r05.bloqueia(p.regras[0])

    # nova conferência mantém a confirmação se a evidência não mudou
    de_novo = r05.avaliar(p)
    assert (
        de_novo.confirmado_por == "Eng. Beltrano"
        and "Confirmado por" in de_novo.mensagem
    )


def test_confirmacao_exige_nome_e_caso_confirmavel(p, monkeypatch):
    _site(monkeypatch, _pagina(descricao="220 V"))
    p.regras = [r05.avaliar(p)]  # aprovada pelo passo 1
    with pytest.raises(ValueError):
        r05.confirmar(p, "Eng. X")
    with pytest.raises(ValueError):
        r05.confirmar(p, "  ")


@pytest.mark.parametrize(
    ("pagina", "trecho"),
    [
        (_pagina(status="Cancelado"), "Cancelado"),
        (_pagina(modelo="OUTRO-MODELO"), "não aparece"),
    ],
)
def test_passo4_inativo_ou_modelo_ausente_reprova(p, monkeypatch, pagina, trecho):
    _site(monkeypatch, pagina)
    r = r05.avaliar(p)
    assert r.status == StatusRegra.REPROVADA and trecho in r.mensagem
    assert r05.bloqueia(r)


def test_registro_sintetico_nao_consulta_e_nunca_aprova(
    processo, monkeypatch, tmp_path
):
    monkeypatch.setattr(r05, "CATALOGO", tmp_path / "vazio.json")
    chamadas = _site(monkeypatch, _pagina(descricao="220 V"))
    r = r05.avaliar(processo)  # fixture: SIMULADO-000000/2026
    assert r.status == StatusRegra.INCERTA and chamadas == []


def test_sem_numero_pede_o_registro(p, monkeypatch):
    p.kit.inversor.certificado_inmetro = None
    _site(monkeypatch, falha=True)
    assert "Informe o número" in r05.avaliar(p).mensagem


def test_catalogo_do_repositorio_so_tem_candidatos_ate_alguem_conferir():
    # Nenhuma entrada do catálogo versionado pode estar "verificada" sem nome e data.
    dados = json.loads(r05.CATALOGO.read_text(encoding="utf-8"))["inversores"]
    for e in dados:
        assert bool(e["verificado_por"]) == bool(e["verificado_em"])


def test_site_fora_do_ar_sem_catalogo_engenheiro_resolve(p, monkeypatch):
    _site(monkeypatch, falha=True)
    r = r05.avaliar(p)
    assert r.status == StatusRegra.INCERTA
    assert r.valores["confirmavel"] == "sim"
    assert "Não foi possível consultar" in r.mensagem
    assert [e.fonte for e in r.evidencias] == ["datasheet"]
    p.regras = [r]
    r05.confirmar(p, "Eng. Beltrano")
    assert not r05.bloqueia(p.regras[0])


def test_quando_o_site_volta_a_confirmacao_precisa_ser_refeita(p, monkeypatch):
    _site(monkeypatch, falha=True)
    p.regras = [r05.avaliar(p)]
    r05.confirmar(p, "Eng. Beltrano")
    _site(monkeypatch, _pagina())  # agora responde: evidência nova
    de_novo = r05.avaliar(p)
    assert de_novo.status == StatusRegra.INCERTA and de_novo.confirmado_por is None


def test_sintetico_ou_tensao_diferente_nao_sao_confirmaveis(p, processo, monkeypatch):
    _site(monkeypatch, falha=True)
    p.kit.inversor.tensao_saida_v = 127
    r = r05.avaliar(p)
    assert r.status == StatusRegra.INCERTA and "confirmavel" not in r.valores
    p.regras = [r]
    with pytest.raises(ValueError):
        r05.confirmar(p, "Eng. X")
    assert r05.bloqueia(r)
