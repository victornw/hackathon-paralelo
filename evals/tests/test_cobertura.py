import pandas as pd
import pytest

from evals import run

DOC_INC = "Documentação incompleta"
DOC_ERR = "Documentação incorreta"
OUTRAS = "Outras não conformidades"
NAO_APROVOU = "Não aprovação nos prazos estabelecidos (art. 83, § 7º, I)"
VIST_NAO = "Vistoria não solicitada"
VIST_REPROV = "Vistoria reprovada, aguardando nova solicitação"
NEGADO = "Pedidos Negados"
ESTOQUE = "Pedidos em Estoque"
CONECTADO = "Pedidos Conectados"


def _l(
    agente="Enel CE",
    protocolo=1,
    envio="2024-01-01",
    solicitacao="2022-06-01",
    potencia=5.0,
    subgrupo="B1",
    fonte="UFV",
    status=NEGADO,
    motivo=DOC_INC,
    situacao="Solicitação de orçamento indeferida (art. 71, II)",
):
    return {
        "SigAgenteDistribuicao": agente,
        "NumProtocolo": protocolo,
        "DatPrzEnvio": envio,
        "DatSolicitacao": solicitacao,
        "MdaPotencia": potencia,
        "DscSubgrupoTarifario": subgrupo,
        "DscFonteGeracao": fonte,
        "DscStatusConexao": status,
        "DscMotivoSituacao": motivo,
        "DscSituacaoConexao": situacao,
    }


def _vistoria(protocolo, situacao, **kw):
    return _l(protocolo=protocolo, status=ESTOQUE, motivo=None, situacao=situacao, **kw)


LINHAS = [
    # protocolo 1 reenviado: só o último envio vale (conectado, não é problema)
    _l(protocolo=1, envio="2023-01-01", motivo=OUTRAS),
    _l(protocolo=1, envio="2024-01-01", status=CONECTADO, motivo=None),
    # cobertos
    _l(protocolo=2, motivo=DOC_INC),
    _l(protocolo=3, motivo=DOC_INC),
    _l(protocolo=4, motivo=DOC_ERR),
    _vistoria(5, VIST_NAO),
    # não cobertos
    _l(protocolo=6, motivo=OUTRAS),
    _vistoria(7, VIST_REPROV),
    # mesma chave em outra distribuidora não colide
    _l(agente="Coelba", protocolo=2, motivo=OUTRAS),
    _l(agente="Coelba", protocolo=8, motivo=NAO_APROVOU),
    # fora da coorte
    _l(protocolo=10, subgrupo="B2"),
    _l(protocolo=11, potencia=10.5),
    _l(protocolo=12, potencia=0.0),
    _l(protocolo=13, fonte="EOL"),
    _l(protocolo=14, solicitacao="2022-01-06"),
    _l(protocolo=15, solicitacao="2023-01-08"),
    # limites inclusivos da coorte
    _l(protocolo=16, solicitacao="2022-01-07", potencia=10.0, motivo=DOC_ERR),
    _l(protocolo=17, solicitacao="2023-01-07", motivo=OUTRAS),
]


@pytest.fixture(params=["parquet", "csv", "zip"])
def arquivo(request, tmp_path):
    df = pd.DataFrame(LINHAS)
    if request.param == "parquet":
        caminho = tmp_path / "base.parquet"
        df.to_parquet(caminho)
    else:
        caminho = tmp_path / f"base.{request.param}"
        df.to_csv(
            caminho,
            sep=";",
            decimal=",",
            index=False,
            encoding="utf-8-sig",
            compression="zip" if request.param == "zip" else None,
        )
    return caminho


def _por_metrica(linhas):
    return {r["metrica"]: r for r in linhas}


def test_coorte_dedup_e_filtros():
    coorte = run.coorte_aneel(pd.DataFrame(LINHAS))
    chaves = set(zip(coorte.SigAgenteDistribuicao, coorte.NumProtocolo.astype(str)))
    assert chaves == {
        ("Enel CE", p) for p in ("1", "2", "3", "4", "5", "6", "7", "16", "17")
    } | {("Coelba", "2"), ("Coelba", "8")}
    ultimo = coorte[
        (coorte.SigAgenteDistribuicao == "Enel CE") & (coorte.NumProtocolo == "1")
    ]
    assert ultimo.DscStatusConexao.iloc[0] == CONECTADO


def test_dedup_empate_fica_com_ultima_linha():
    linhas = [
        _l(protocolo=1, envio="2024-01-01", motivo=OUTRAS),
        _l(protocolo=1, envio="2024-01-01", motivo=DOC_INC),
    ]
    coorte = run.coorte_aneel(pd.DataFrame(linhas))
    assert coorte.DscMotivoSituacao.tolist() == [DOC_INC]


def test_linhas_sem_chave_ou_envio_caem():
    linhas = [
        _l(protocolo=1),
        _l(protocolo=2, envio=None),
        _l(agente="", protocolo=3),
    ]
    coorte = run.coorte_aneel(pd.DataFrame(linhas))
    assert coorte.NumProtocolo.tolist() == ["1"]


def test_cobertura_percentual_e_contagens(arquivo):
    m = _por_metrica(run.cobertura_aneel(arquivo))
    # Enel CE: negados 2,3,4,6,16,17 (6) + vistorias 5,7 (2) = 8 casos; cobertos 2,3,4,5,16 = 5
    assert (
        m["ANEEL Enel CE: casos-problema (negados + vistoria parada)"]["valor"] == "8"
    )
    cob = m["ANEEL Enel CE: casos-problema em categorias cobertas"]
    assert cob["valor"] == run.pct(5 / 8)
    assert cob["base"] == "5 de 8 casos-problema"
    assert m[f"ANEEL Enel CE: {DOC_INC}"]["valor"] == "2"
    assert m[f"ANEEL Enel CE: {DOC_ERR}"]["valor"] == "2"
    assert VIST_NAO not in "".join(m)  # só as duas maiores categorias cobertas
    # Nordeste soma Coelba: +2 casos, +1 coberto (prazos)
    assert (
        m["ANEEL Nordeste: casos-problema (negados + vistoria parada)"]["valor"] == "10"
    )
    assert m["ANEEL Nordeste: casos-problema em categorias cobertas"][
        "valor"
    ] == run.pct(6 / 10)
    assert m[f"ANEEL Nordeste: {DOC_INC}"]["valor"] == "2"
    assert all(run.OBS_ANEEL in r["obs"] for r in m.values())


def test_vistoria_reprovada_nao_e_coberta():
    assert run.COBERTURA[VIST_REPROV] == "nao_coberto"
    assert run.COBERTURA[VIST_NAO] == "coberto"
    assert OUTRAS not in run.COBERTURA


def test_coluna_ausente_vira_nao_medido(tmp_path):
    caminho = tmp_path / "base.parquet"
    pd.DataFrame(LINHAS).drop(columns=["DscMotivoSituacao"]).to_parquet(caminho)
    (linha,) = run.cobertura_aneel(caminho)
    assert linha["valor"] == run.NAO_MEDIDO
    assert "DscMotivoSituacao" in linha["obs"]


def _zip_csv(caminho, linhas):
    """Escreve um ZIP com um CSV no formato do portal (separador ';', decimal ',')."""
    import zipfile

    df = pd.DataFrame(linhas)
    df["MdaPotencia"] = df["MdaPotencia"].map(lambda v: str(v).replace(".", ","))
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("pedidos.csv", df.to_csv(sep=";", index=False))


def test_pasta_com_varias_regioes_junta_tudo_e_traz_o_brasil(tmp_path):
    pasta = tmp_path / "zips"
    pasta.mkdir()
    # Equatorial AL dividida entre dois arquivos regionais, como na base real
    _zip_csv(
        pasta / "nordeste.zip",
        [
            _l(agente="Equatorial AL", protocolo=10, motivo=DOC_INC),
            _l(agente="Enel CE", protocolo=11, status=CONECTADO, motivo=None),
        ],
    )
    _zip_csv(
        pasta / "norte.zip",
        [
            _l(agente="Equatorial AL", protocolo=12, motivo=DOC_INC),
            _l(agente="Equatorial AL", protocolo=13, motivo=OUTRAS),
        ],
    )
    _zip_csv(
        pasta / "sudeste.zip", [_l(agente="Cemig-D", protocolo=20, motivo=DOC_ERR)]
    )

    linhas = run.secao_aneel(pasta)
    texto = (
        run.tabela_markdown(linhas) if hasattr(run, "tabela_markdown") else str(linhas)
    )
    assert "ANEEL Brasil: casos-problema" in texto
    assert "Equatorial AL: 3 pedidos" in texto  # os dois arquivos somados
    assert "Cemig-D" in texto and "Enel CE" in texto


def test_pasta_inexistente_continua_nao_medido(tmp_path):
    (linha,) = run.secao_aneel(tmp_path / "nao_existe")
    assert "não encontrada" in str(linha)
