"""API HTTP com TestClient. O fluxo de ponta a ponta usa as ferramentas reais
(verificador, perguntas, conferidor, documentos, portal simulado) e só a
extração por LLM é falsa."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core import extracao, regras
from app.core import repositorio as repo
from app.main import app
from app.schemas import (
    Camada,
    CampoExtraido,
    DadosVisita,
    DocumentoGerado,
    Etapa,
    Fonte,
    Pergunta,
    Processo,
    ResultadoRegra,
    StatusRegra,
)
from app.tracing import trace as registrar_trace

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("DOCS_DIR", str(tmp_path / "docs"))
    monkeypatch.setenv("RELOGIO_INICIO", "2026-11-09")
    monkeypatch.setenv("ORQUESTRADOR_ESPERA_S", "0")
    monkeypatch.delenv("FEATHERLESS_API_KEY", raising=False)


@pytest.fixture
def cliente() -> TestClient:
    return TestClient(app)


@pytest.fixture
def modelo() -> Processo:
    return Processo.model_validate_json(
        (FIXTURES / "processo_exemplo.json").read_text()
    )


@pytest.fixture
def extracao_falsa(monkeypatch, modelo):
    chamadas = []
    monkeypatch.setattr(
        extracao, "extrair_conta", lambda a: chamadas.append(a.name) or modelo.campos
    )
    monkeypatch.setattr(
        extracao, "extrair_kit", lambda arquivos: chamadas.append("kit") or modelo.kit
    )
    monkeypatch.setattr(
        extracao,
        "extrair_padrao",
        lambda foto: (
            chamadas.append(foto.name)
            or DadosVisita(
                disjuntor_padrao_a=modelo.visita.disjuntor_padrao_a,
                polos_padrao=modelo.visita.polos_padrao,
            )
        ),
    )
    return chamadas


def enviar(cliente, pid, tipo, nome, conteudo=b"conteudo"):
    return cliente.post(
        f"/api/processos/{pid}/arquivos",
        data={"tipo": tipo},
        files={"file": (nome, conteudo)},
    )


def perguntar(pid, campo, destinatario="integrador", **extra) -> None:
    repo.atualizar(
        pid,
        lambda q: q.perguntas.append(
            Pergunta(
                id=campo, campo=campo, texto="?", destinatario=destinatario, **extra
            )
        ),
    )


def responder(cliente, pid, campo, texto):
    return cliente.post(
        f"/api/processos/{pid}/respostas", json=[{"id": campo, "resposta": texto}]
    )


# --- processos -----------------------------------------------------------------------------


def test_criar_listar_e_obter(cliente):
    criado = cliente.post("/api/processos", json={"email_contato": "a@b.com"})
    assert criado.status_code == 201
    pid = criado.json()["id"]
    assert cliente.post("/api/processos").status_code == 201
    assert cliente.get("/api/processos").json()[0]["id"] == pid
    assert cliente.get(f"/api/processos/{pid}").json()["email_contato"] == "a@b.com"


@pytest.mark.parametrize(
    "metodo,rota,corpo",
    [
        ("get", "/api/processos/x", None),
        ("post", "/api/processos/x/rodar", None),
        ("post", "/api/processos/x/respostas", []),
        ("post", "/api/processos/x/revisao", {"engenheiro": "E"}),
        ("post", "/api/processos/x/portal/aprovar-orcamento", None),
        ("get", "/api/processos/x/trace", None),
        ("get", "/api/processos/x/documentos/a.pdf", None),
    ],
)
def test_processo_inexistente_responde_404(cliente, metodo, rota, corpo):
    resposta = getattr(cliente, metodo)(
        rota, **({"json": corpo} if corpo is not None else {})
    )
    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "Processo não encontrado."


# --- arquivos --------------------------------------------------------------------------------------


def test_upload_guarda_o_arquivo_e_roda_o_orquestrador(cliente, extracao_falsa):
    pid = cliente.post("/api/processos").json()["id"]
    resposta = enviar(cliente, pid, "conta", "conta.pdf", b"abc")
    assert resposta.status_code == 200
    caminho = Path(resposta.json()["caminho"])
    assert caminho.read_bytes() == b"abc" and caminho.parent.name == "conta"
    assert extracao_falsa == ["conta.pdf"]
    assert "uc" in cliente.get(f"/api/processos/{pid}").json()["campos"]


def test_upload_com_tipo_invalido_422(cliente):
    pid = cliente.post("/api/processos").json()["id"]
    assert enviar(cliente, pid, "outro", "x.pdf").status_code == 422


def test_upload_depois_do_protocolo_409(cliente):
    pid = cliente.post("/api/processos").json()["id"]
    repo.atualizar(pid, lambda q: setattr(q, "etapa", Etapa.PROTOCOLADO))
    assert enviar(cliente, pid, "conta", "conta.pdf").status_code == 409


def test_upload_durante_a_revisao_invalida_a_aprovacao(cliente, extracao_falsa):
    pid = cliente.post("/api/processos").json()["id"]

    def em_revisao(q):
        q.etapa = Etapa.EM_REVISAO
        q.revisado_por = "Eng."

    repo.atualizar(pid, em_revisao)
    enviar(cliente, pid, "conta", "conta.pdf")
    p = repo.carregar(pid)
    assert p.etapa == Etapa.MONTAGEM and p.revisado_por is None


# --- respostas ---------------------------------------------------------------------------------------


def test_resposta_a_pergunta_desconhecida_404_e_nada_muda(cliente):
    pid = cliente.post("/api/processos").json()["id"]
    perguntar(pid, "telefone")
    resposta = cliente.post(
        f"/api/processos/{pid}/respostas",
        json=[
            {"id": "telefone", "resposta": "1"},
            {"id": "nao-existe", "resposta": "2"},
        ],
    )
    assert resposta.status_code == 404 and "nao-existe" in resposta.json()["detail"]
    assert repo.carregar(pid).perguntas[0].resposta is None


def test_resposta_sem_mapeamento_so_fica_guardada_com_a_data(cliente):
    pid = cliente.post("/api/processos").json()["id"]
    perguntar(pid, "telefone")
    p = responder(cliente, pid, "telefone", "85999990000").json()
    assert p["perguntas"][0]["resposta"] == "85999990000"
    assert p["perguntas"][0]["respondida_em"].startswith("2026-11-09")


def test_resposta_invalida_422_e_nao_grava_nenhuma(cliente):
    pid = cliente.post("/api/processos").json()["id"]
    perguntar(pid, "bitola_ca_mm2")
    perguntar(pid, "tipo_ramal")
    resposta = cliente.post(
        f"/api/processos/{pid}/respostas",
        json=[
            {"id": "bitola_ca_mm2", "resposta": "4"},
            {"id": "tipo_ramal", "resposta": "não sei"},
        ],
    )
    assert resposta.status_code == 422
    p = repo.carregar(pid)
    assert p.visita.bitola_ca_mm2 is None and all(
        q.resposta is None for q in p.perguntas
    )


def _confirmado(campo: CampoExtraido, valor):
    assert campo.valor == valor and campo.confianca == 1
    assert campo.fonte.documento == "resposta_integrador"


CASOS_DE_RESPOSTA = [
    (
        "disjuntor_padrao_a",
        "50 A",
        lambda p: _confirmado(p.visita.disjuntor_padrao_a, 50),
    ),
    (
        "bitola_ca_mm2",
        "2,5 mm²",
        lambda p: p.visita.bitola_ca_mm2 == 2.5 or pytest.fail(),
    ),
    (
        "distancia_inversor_quadro_m",
        "12",
        lambda p: p.visita.distancia_inversor_quadro_m == 12,
    ),
    (
        "coordenadas_padrao",
        "-3,7319, -38,5267",
        lambda p: (p.visita.latitude, p.visita.longitude) == (-3.7319, -38.5267),
    ),
    ("latitude", "-3.7", lambda p: p.visita.latitude == -3.7),
    ("tipo_ramal", "Subterrâneo", lambda p: p.visita.tipo_ramal == "subterraneo"),
    (
        "email_contato",
        " novo@exemplo.com ",
        lambda p: p.email_contato == "novo@exemplo.com",
    ),
    (
        "campos.titular",
        "Maria Silva",
        lambda p: _confirmado(p.campos["titular"], "Maria Silva"),
    ),
    (
        "campos.tensao_atendimento_v",
        "220 V",
        lambda p: _confirmado(p.campos["tensao_atendimento_v"], 220),
    ),
    (
        "campos.tipo_ligacao",
        "Monofásico",
        lambda p: _confirmado(p.campos["tipo_ligacao"], "monofasico"),
    ),
]


@pytest.mark.parametrize("campo,texto,confere", CASOS_DE_RESPOSTA)
def test_resposta_vira_dado_do_processo(cliente, campo, texto, confere):
    pid = cliente.post("/api/processos").json()["id"]
    perguntar(pid, campo)
    assert responder(cliente, pid, campo, texto).status_code == 200
    assert confere(repo.carregar(pid)) is not False


def test_confirmar_campo_da_conta_mantem_o_valor_lido_e_sobe_a_confianca(cliente):
    pid = cliente.post("/api/processos").json()["id"]
    lido = CampoExtraido(
        valor="MARIA", confianca=0.5, fonte=Fonte(documento="conta.pdf")
    )
    repo.atualizar(pid, lambda q: q.campos.update(titular=lido))
    perguntar(pid, "campos.titular")
    responder(cliente, pid, "campos.titular", "Sim, está correto")
    _confirmado(repo.carregar(pid).campos["titular"], "MARIA")


def test_confirmar_campo_ilegivel_sem_valor_pede_o_valor(cliente):
    pid = cliente.post("/api/processos").json()["id"]
    perguntar(pid, "campos.titular")
    assert responder(cliente, pid, "campos.titular", "sim").status_code == 422


def test_relacao_de_cargas_em_linhas(cliente):
    pid = cliente.post("/api/processos").json()["id"]
    perguntar(pid, "relacao_cargas")
    texto = "geladeira 150\nar-condicionado 12.000 BTU 1400 W x2\nchuveiro 5,5 kW\nforno 1.500 w × 3\n"
    responder(cliente, pid, "relacao_cargas", texto)
    cargas = [
        (c.descricao, c.potencia_w, c.quantidade)
        for c in repo.carregar(pid).visita.relacao_cargas
    ]
    assert cargas == [
        ("geladeira", 150, 1),
        ("ar-condicionado 12.000 BTU", 1400, 2),
        ("chuveiro", 5500, 1),
        ("forno", 1500, 3),
    ]


def test_relacao_de_cargas_em_json(cliente):
    pid = cliente.post("/api/processos").json()["id"]
    perguntar(pid, "relacao_cargas")
    responder(
        cliente,
        pid,
        "relacao_cargas",
        '[{"descricao": "TV", "potencia_w": 100, "quantidade": 2}]',
    )
    assert repo.carregar(pid).visita.relacao_cargas[0].quantidade == 2


@pytest.mark.parametrize("texto", ["", "   \n", "geladeira", "algumas lâmpadas"])
def test_relacao_de_cargas_ilegivel_422(cliente, texto):
    pid = cliente.post("/api/processos").json()["id"]
    perguntar(pid, "relacao_cargas")
    resposta = cliente.post(
        f"/api/processos/{pid}/respostas",
        json=[{"id": "relacao_cargas", "resposta": texto}],
    )
    assert resposta.status_code == 422


def test_confirmar_strings_sugeridas(cliente, modelo):
    pid = cliente.post("/api/processos").json()["id"]

    def com_kit(q):
        q.kit = modelo.kit
        for s in q.kit.strings:
            s.sugerida = True

    repo.atualizar(pid, com_kit)
    perguntar(pid, "strings", "engenheiro")
    responder(cliente, pid, "strings", "sim")
    assert not any(s.sugerida for s in repo.carregar(pid).kit.strings)


def test_informar_strings_por_mppt(cliente, modelo):
    pid = cliente.post("/api/processos").json()["id"]
    repo.atualizar(
        pid, lambda q: setattr(q, "kit", modelo.kit.model_copy(update={"strings": []}))
    )
    perguntar(pid, "strings")
    responder(cliente, pid, "strings", "MPPT1: 7, MPPT2: 6")
    strings = repo.carregar(pid).kit.strings
    assert [(s.mppt, s.modulos_em_serie, s.sugerida) for s in strings] == [
        (1, 7, False),
        (2, 6, False),
    ]


def test_dados_do_kit_vindos_de_resposta(cliente, modelo):
    pid = cliente.post("/api/processos").json()["id"]
    repo.atualizar(pid, lambda q: setattr(q, "kit", modelo.kit))
    perguntar(pid, "coef_temp_voc_pct_c")
    perguntar(pid, "certificado_inmetro")
    cliente.post(
        f"/api/processos/{pid}/respostas",
        json=[
            {"id": "coef_temp_voc_pct_c", "resposta": "-0,27"},
            {"id": "certificado_inmetro", "resposta": "004567/2024"},
        ],
    )
    kit = repo.carregar(pid).kit
    assert kit.modulo.coef_temp_voc_pct_c == -0.27
    assert kit.inversor.certificado_inmetro == "004567/2024"


def test_coeficiente_positivo_e_recusado(cliente, modelo):
    pid = cliente.post("/api/processos").json()["id"]
    repo.atualizar(pid, lambda q: setattr(q, "kit", modelo.kit))
    perguntar(pid, "coef_temp_voc_pct_c")
    assert responder(cliente, pid, "coef_temp_voc_pct_c", "0,27").status_code == 422


def test_dado_do_kit_sem_kit_lido_422(cliente):
    pid = cliente.post("/api/processos").json()["id"]
    perguntar(pid, "certificado_inmetro")
    assert responder(cliente, pid, "certificado_inmetro", "123").status_code == 422


def test_resposta_na_revisao_volta_para_a_montagem(cliente):
    """Toda resposta pode ir para os documentos (telefone no Anexo A, DPS no memorial)."""
    pid = cliente.post("/api/processos").json()["id"]

    def em_revisao(q):
        q.etapa = Etapa.EM_REVISAO
        q.revisado_por = "Eng."

    for campo, valor in (("telefone", "1"), ("bitola_ca_mm2", "6")):
        repo.atualizar(pid, em_revisao)
        perguntar(pid, campo)
        responder(cliente, pid, campo, valor)
        p = repo.carregar(pid)
        assert p.etapa == Etapa.MONTAGEM and p.revisado_por is None


# --- revisão, relógio, documentos, trace --------------------------------------------------------------


def regra(status):
    return ResultadoRegra(
        regra_id="R01",
        descricao="x",
        camada=Camada.TECNICA,
        status=status,
        mensagem="m",
        fonte_norma="n",
    )


def regras_simuladas_aprovadas():
    """Só para isolar os testes de revisão e portal da validação técnica."""
    return [
        regra(StatusRegra.APROVADA).model_copy(update={"regra_id": f"R0{i}"})
        for i in range(6)
    ]


def test_revisao_grava_engenheiro_e_data(cliente, monkeypatch):
    monkeypatch.setattr(regras, "conferir", lambda p: regras_simuladas_aprovadas())
    pid = cliente.post("/api/processos").json()["id"]
    repo.atualizar(pid, lambda q: setattr(q, "etapa", Etapa.EM_REVISAO))
    repo.atualizar(pid, lambda q: setattr(q, "regras", regras_simuladas_aprovadas()))
    p = cliente.post(
        f"/api/processos/{pid}/revisao", json={"engenheiro": " Eng. Ana "}
    ).json()
    assert p["revisado_por"] == "Eng. Ana" and p["revisado_em"].startswith("2026-11-09")


def test_revisao_fora_da_etapa_409(cliente):
    pid = cliente.post("/api/processos").json()["id"]
    resposta = cliente.post(
        f"/api/processos/{pid}/revisao", json={"engenheiro": "Eng."}
    )
    assert resposta.status_code == 409 and "montagem" in resposta.json()["detail"]


def test_revisao_com_regra_reprovada_409(cliente):
    pid = cliente.post("/api/processos").json()["id"]

    def mudar(q):
        q.etapa = Etapa.EM_REVISAO
        q.regras = [regra(StatusRegra.REPROVADA)]

    repo.atualizar(pid, mudar)
    assert (
        cliente.post(
            f"/api/processos/{pid}/revisao", json={"engenheiro": "Eng."}
        ).status_code
        == 409
    )
    assert repo.carregar(pid).revisado_por is None


def test_revisao_sem_nome_422(cliente):
    pid = cliente.post("/api/processos").json()["id"]
    assert (
        cliente.post(
            f"/api/processos/{pid}/revisao", json={"engenheiro": ""}
        ).status_code
        == 422
    )


def test_rodar_aceita_e_refazer_libera_passo_com_falha(
    cliente, extracao_falsa, monkeypatch
):
    ligada = {"quebrada": True}
    original = extracao.extrair_conta

    def conta(arquivo):
        if ligada["quebrada"]:
            raise RuntimeError("fora do ar")
        return original(arquivo)

    monkeypatch.setattr(extracao, "extrair_conta", conta)
    pid = cliente.post("/api/processos").json()["id"]
    enviar(cliente, pid, "conta", "conta.pdf")
    assert any(q.id == "falha:extrair_conta" for q in repo.carregar(pid).perguntas)
    ligada["quebrada"] = False
    assert cliente.post(f"/api/processos/{pid}/rodar").status_code == 202
    assert not repo.carregar(pid).campos
    assert cliente.post(f"/api/processos/{pid}/rodar?refazer=true").status_code == 202
    p = repo.carregar(pid)
    assert p.campos and not any(q.id == "falha:extrair_conta" for q in p.perguntas)


def test_acao_do_portal_antes_do_protocolo_409(cliente):
    pid = cliente.post("/api/processos").json()["id"]
    assert (
        cliente.post(f"/api/processos/{pid}/portal/solicitar-vistoria").status_code
        == 409
    )


def test_avancar_relogio(cliente):
    assert cliente.post("/api/relogio/avancar", json={"dias": 3}).json() == {
        "hoje": "2026-11-12"
    }
    assert cliente.post("/api/relogio/avancar", json={"dias": 0}).status_code == 422
    assert cliente.post("/api/relogio/avancar", json={"dias": -1}).status_code == 422


def test_documento_so_serve_o_que_esta_no_processo(cliente, tmp_path):
    pid = cliente.post("/api/processos").json()["id"]
    arquivo = tmp_path / "memorial.pdf"
    arquivo.write_bytes(b"%PDF-1.4 teste")
    segredo = tmp_path / "segredo.txt"
    segredo.write_text("nao serve")
    doc = DocumentoGerado(
        tipo="memorial",
        nome_arquivo="memorial.pdf",
        caminho=str(arquivo),
        formato="pdf",
        gerado_em=repo.agora(),
    )
    repo.atualizar(pid, lambda q: q.documentos.append(doc))
    ok = cliente.get(f"/api/processos/{pid}/documentos/memorial.pdf")
    assert ok.status_code == 200 and ok.content == b"%PDF-1.4 teste"
    assert (
        cliente.get(f"/api/processos/{pid}/documentos/segredo.txt").status_code == 404
    )
    assert (
        cliente.get(f"/api/processos/{pid}/documentos/..%2Fsegredo.txt").status_code
        == 404
    )
    arquivo.unlink()
    assert (
        cliente.get(f"/api/processos/{pid}/documentos/memorial.pdf").status_code == 404
    )


def test_pagina_inicial_e_estaticos(cliente):
    assert cliente.get("/", follow_redirects=False).status_code in (302, 307)
    assert cliente.get("/painel").status_code == 200
    assert cliente.get("/static/painel.css").status_code == 200


# --- ponta a ponta -----------------------------------------------------------------------------------------

RESPOSTAS_DO_INTEGRADOR = {
    "relacao_cargas": "geladeira 150 x1\nar-condicionado 1400 W x2\nchuveiro 5,5 kW",
    "bitola_ca_mm2": "6 mm²",
    "area_concessao": "Ceará",
    "distancia_inversor_quadro_m": "8 m",
    "coordenadas_padrao": "-3,7319, -38,5267",
    "tipo_ramal": "aéreo",
    "telefone": "85999990000",
    "qtd_ucs_credito": "1",
    "modalidade_compensacao": "autoconsumo local",
    "strings": "sim",
    "dps_especificacao": "classe II, 275 V, 20 kA",
}


def preparar_ate_revisao(cliente):
    pid = cliente.post(
        "/api/processos", json={"email_contato": "integrador@exemplo.com"}
    ).json()["id"]
    for tipo, nome in (
        ("conta", "conta.pdf"),
        ("proposta", "proposta.pdf"),
        ("padrao", "foto.jpg"),
    ):
        assert enviar(cliente, pid, tipo, nome).status_code == 200

    p = cliente.get(f"/api/processos/{pid}").json()
    assert p["etapa"] == "montagem" and p["kit"] and p["documentos"]
    abertas = [q for q in p["perguntas"] if not q["resposta"]]
    assert {q["campo"] for q in abertas} == set(RESPOSTAS_DO_INTEGRADOR)

    corpo = [
        {"id": q["id"], "resposta": RESPOSTAS_DO_INTEGRADOR[q["campo"]]}
        for q in abertas
    ]
    p = cliente.post(f"/api/processos/{pid}/respostas", json=corpo).json()
    p = cliente.get(f"/api/processos/{pid}").json()
    assert p["etapa"] == "em_revisao"
    return pid, p


def test_pacote_com_premissas_e_inmetro_pendentes_nao_protocola(
    cliente, extracao_falsa
):
    pid, p = preparar_ate_revisao(cliente)
    regras_ = {r["regra_id"]: r for r in p["regras"] if r["regra_id"] <= "R05"}
    assert {i: r["status"] for i, r in regras_.items()} == {
        "R00": "aprovada",
        "R01": "aprovada",
        "R02": "aprovada",  # com premissas declaradas (método, isolação...)
        "R03": "aprovada",
        "R04": "aprovada",
        "R05": "incerta",  # sem prova de 220 V e sem confirmação do engenheiro
    }
    assert regras_["R02"]["premissas"]
    resposta = cliente.post(
        f"/api/processos/{pid}/revisao", json={"engenheiro": "Eng. Teste"}
    )
    assert resposta.status_code == 409
    detalhe = resposta.json()["detail"]
    assert "R05" in detalhe and "R02" not in detalhe and "R03" not in detalhe
    atual = repo.carregar(pid)
    assert atual.revisado_por is None and atual.numero_solicitacao is None


def test_fluxo_portal_com_conferencia_simulada(cliente, extracao_falsa, monkeypatch):
    # Valida apenas transições do portal. Conformidade real é testada acima,
    # onde o mesmo pacote é bloqueado em vez de receber uma aprovação artificial.
    @registrar_trace("conferir")
    def conferencia_simulada(p):
        return regras_simuladas_aprovadas()

    monkeypatch.setattr(regras, "conferir", conferencia_simulada)
    pid, p = preparar_ate_revisao(cliente)
    assert {
        r["regra_id"]: r["status"] for r in p["regras"] if r["regra_id"] <= "R05"
    } == {f"R0{i}": "aprovada" for i in range(6)}
    assert p["numero_solicitacao"] is None

    assert (
        cliente.post(
            f"/api/processos/{pid}/revisao", json={"engenheiro": "Eng. Teste"}
        ).status_code
        == 200
    )
    p = cliente.get(f"/api/processos/{pid}").json()
    assert p["etapa"] == "protocolado" and p["numero_solicitacao"].startswith(
        "GD-2026-"
    )

    assert cliente.post("/api/relogio/avancar", json={"dias": 1}).json() == {
        "hoje": "2026-11-10"
    }
    p = cliente.get(f"/api/processos/{pid}").json()
    assert p["etapa"] == "pendencia"
    assert p["eventos"][-1]["categoria_pendencia"] == "unifilar_inconsistente"
    assert p["revisado_por"] is None
    assert [x["tipo"] for x in p["prazos"]] == ["sanar_pendencia"]

    cliente.post(f"/api/processos/{pid}/revisao", json={"engenheiro": "Eng. Teste"})
    assert cliente.get(f"/api/processos/{pid}").json()["etapa"] == "protocolado"

    cliente.post("/api/relogio/avancar", json={"dias": 1})
    p = cliente.get(f"/api/processos/{pid}").json()
    assert p["etapa"] == "orcamento_emitido"
    assert (
        p["prazos"][0]["tipo"] == "aprovar_orcamento" and p["prazos"][0]["dias_uteis"]
    )

    assert (
        cliente.post(f"/api/processos/{pid}/portal/aprovar-orcamento").json()["etapa"]
        == "orcamento_aprovado"
    )
    assert (
        cliente.post(f"/api/processos/{pid}/portal/solicitar-vistoria").json()["etapa"]
        == "vistoria_solicitada"
    )
    assert (
        cliente.post(f"/api/processos/{pid}/portal/aprovar-orcamento").status_code
        == 409
    )

    for _ in range(3):
        cliente.post("/api/relogio/avancar", json={"dias": 2})
    p = cliente.get(f"/api/processos/{pid}").json()
    assert p["etapa"] == "concluido" and p["prazos"] == []
    assert p["eventos"][0]["etapa"] == "protocolado"

    nome = next(d["nome_arquivo"] for d in p["documentos"] if d["tipo"] == "memorial")
    assert (
        cliente.get(f"/api/processos/{pid}/documentos/{nome}").headers["content-type"]
        == "application/pdf"
    )

    trace = cliente.get(f"/api/processos/{pid}/trace").json()
    nomes = {x["passo"] for x in trace["passos"]}
    assert {
        "decidir_proximo_passo",
        "gerar_documentos",
        "conferir",
        "protocolar",
        "reenviar",
    } <= nomes
    assert (
        trace["resumo_custo"]["passos"] == len(trace["passos"])
        and trace["resumo_custo"]["erros"] == 0
    )
    assert cliente.get(f"/processos/{pid}/timeline").status_code == 200


def test_concluido_nao_e_tocado_pelo_relogio(cliente):
    pid = cliente.post("/api/processos").json()["id"]
    repo.atualizar(pid, lambda q: setattr(q, "etapa", Etapa.CONCLUIDO))
    cliente.post("/api/relogio/avancar", json={"dias": 5})
    assert repo.carregar(pid).etapa == Etapa.CONCLUIDO


@pytest.mark.parametrize(
    "problema", ["ausente", "incerta", "nao_verificada", "a_validar", "duplicada"]
)
def test_api_nao_aprova_regra_obrigatoria_sem_conclusao(cliente, problema):
    pid = cliente.post("/api/processos").json()["id"]

    def preparar(p):
        p.etapa = Etapa.EM_REVISAO
        p.regras = regras_simuladas_aprovadas()
        if problema == "ausente":
            p.regras.pop()
        elif problema == "a_validar":
            p.regras[-1].a_validar = True
        elif problema == "duplicada":
            p.regras.append(p.regras[-1].model_copy())
        else:
            p.regras[-1].status = StatusRegra(problema)

    repo.atualizar(pid, preparar)
    r = cliente.post(f"/api/processos/{pid}/revisao", json={"engenheiro": "Eng. Teste"})
    assert r.status_code == 409 and "R05" in r.json()["detail"]
    assert repo.carregar(pid).revisado_por is None
    assert repo.carregar(pid).numero_solicitacao is None


def test_aprovacao_refaz_conferencia_e_nao_confia_em_resultados_antigos(cliente):
    pid = cliente.post("/api/processos").json()["id"]

    def preparar(p):
        p.etapa = Etapa.EM_REVISAO
        p.regras = regras_simuladas_aprovadas()

    repo.atualizar(pid, preparar)
    r = cliente.post(f"/api/processos/{pid}/revisao", json={"engenheiro": "Eng. Teste"})
    assert r.status_code == 409
    atual = repo.carregar(pid)
    assert atual.revisado_por is None and atual.numero_solicitacao is None
    assert any(x.status == StatusRegra.INCERTA for x in atual.regras)


def test_cabo_de_4_mm2_com_disjuntor_de_25_a_reprova_e_nao_vai_para_revisao(
    cliente, extracao_falsa
):
    respostas = dict(RESPOSTAS_DO_INTEGRADOR, bitola_ca_mm2="4 mm²")
    pid = cliente.post(
        "/api/processos", json={"email_contato": "integrador@exemplo.com"}
    ).json()["id"]
    for tipo, nome in (
        ("conta", "conta.pdf"),
        ("proposta", "proposta.pdf"),
        ("padrao", "foto.jpg"),
    ):
        enviar(cliente, pid, tipo, nome)
    p = cliente.get(f"/api/processos/{pid}").json()
    corpo = [
        {"id": q["id"], "resposta": respostas[q["campo"]]}
        for q in p["perguntas"]
        if not q["resposta"]
    ]
    cliente.post(f"/api/processos/{pid}/respostas", json=corpo)
    p = cliente.get(f"/api/processos/{pid}").json()
    r02 = next(r for r in p["regras"] if r["regra_id"] == "R02")
    assert r02["status"] == "reprovada" and "capacidade corrigida" in r02["mensagem"]
    assert p["etapa"] == "montagem"


def test_area_de_concessao_invalida_e_recusada(cliente, extracao_falsa):
    pid = cliente.post("/api/processos", json={}).json()["id"]
    for tipo, nome in (("conta", "conta.pdf"), ("proposta", "proposta.pdf")):
        enviar(cliente, pid, tipo, nome)
    p = cliente.get(f"/api/processos/{pid}").json()
    q = next(q for q in p["perguntas"] if q["campo"] == "area_concessao")
    r = cliente.post(
        f"/api/processos/{pid}/respostas", json=[{"id": q["id"], "resposta": "Marte"}]
    )
    assert r.status_code == 422
    r = cliente.post(
        f"/api/processos/{pid}/respostas",
        json=[{"id": q["id"], "resposta": "RJ Sul Fluminense"}],
    )
    assert r.status_code == 200
    assert repo.carregar(pid).visita.area_concessao == "rj_sul_fluminense"
