"""Orquestrador com ferramentas falsas (as reais têm teste próprio) e o portal simulado real."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core import extracao, orquestrador, perguntas
from app.core import regras as conferidor
from app.core import repositorio as repo
from app.core.orquestrador import Passo, orquestrar, passos_disponiveis
from app.docs import gerar as gerador
from app.portal_sim import portal
from app.schemas import (
    Camada,
    Carga,
    DocumentoGerado,
    Etapa,
    Pergunta,
    Processo,
    ResultadoRegra,
    StatusRegra,
)
from app.tracing import listar_passos

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
RESPOSTAS_DO_PORTAL = {
    "telefone": "85999990000",
    "qtd_ucs_credito": "1",
    "modalidade_compensacao": "autoconsumo local",
}


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("RELOGIO_INICIO", "2026-11-09")
    monkeypatch.setenv("ORQUESTRADOR_ESPERA_S", "0")
    monkeypatch.delenv("FEATHERLESS_API_KEY", raising=False)


@pytest.fixture
def modelo() -> Processo:
    p = Processo.model_validate_json((FIXTURES / "processo_exemplo.json").read_text())
    p.visita.relacao_cargas = [Carga(descricao="chuveiro", potencia_w=5500)]
    return p


@pytest.fixture
def ferramentas(monkeypatch, modelo):
    """Ferramentas falsas com contador de chamadas; `ctx.pendentes` controla as perguntas."""
    ctx = SimpleNamespace(
        chamadas={}, pendentes=[], status=StatusRegra.APROVADA, ao_extrair_conta=None
    )

    def contar(nome):
        ctx.chamadas[nome] = ctx.chamadas.get(nome, 0) + 1

    def extrair_conta(arquivo):
        contar("extrair_conta")
        if ctx.ao_extrair_conta:
            ctx.ao_extrair_conta()
        return modelo.campos

    def extrair_kit(arquivos):
        contar("extrair_kit")
        return modelo.kit

    def extrair_padrao(foto):
        contar("extrair_padrao")
        return modelo.visita

    def verificar_arranjo(kit, visita):
        contar("verificar_arranjo")
        return kit, visita, []

    def perguntas_pendentes(p):
        contar("perguntas_pendentes")
        return [
            Pergunta(id=c, campo=c, texto=f"Qual {c}?")
            for c in ctx.pendentes
            if not any(q.id == c and q.resposta for q in p.perguntas)
        ]

    def conferir(p):
        contar("conferir")
        return [
            ResultadoRegra(
                regra_id=f"R0{i}",
                descricao="x",
                camada=Camada.TECNICA,
                status=ctx.status,
                mensagem="ok",
                fonte_norma="NBR",
            )
            for i in range(6)
        ]

    def gerar_documentos(p):
        contar("gerar_documentos")
        return [
            DocumentoGerado(
                tipo="memorial",
                nome_arquivo="memorial.pdf",
                caminho="/tmp/memorial.pdf",
                formato="pdf",
                gerado_em=repo.agora(),
            )
        ]

    monkeypatch.setattr(extracao, "extrair_conta", extrair_conta)
    monkeypatch.setattr(extracao, "extrair_kit", extrair_kit)
    monkeypatch.setattr(extracao, "extrair_padrao", extrair_padrao)
    monkeypatch.setattr(orquestrador.arranjo, "verificar_arranjo", verificar_arranjo)
    monkeypatch.setattr(perguntas, "perguntas_pendentes", perguntas_pendentes)
    monkeypatch.setattr(conferidor, "conferir", conferir)
    monkeypatch.setattr(gerador, "gerar_documentos", gerar_documentos)
    return ctx


def novo_processo(com_arquivos: bool = True) -> str:
    p = repo.criar("integrador@exemplo.com")
    if com_arquivos:
        repo.guardar_arquivo(p.id, "conta", "conta.pdf", b"conta")
        repo.guardar_arquivo(p.id, "proposta", "proposta.pdf", b"proposta")
        repo.guardar_arquivo(p.id, "padrao", "foto.jpg", b"foto")
    respondidas = [
        Pergunta(id=c, campo=c, texto="?", resposta=r)
        for c, r in RESPOSTAS_DO_PORTAL.items()
    ]
    repo.atualizar(p.id, lambda q: q.perguntas.extend(respondidas))
    return p.id


def aprovar(pid: str, engenheiro: str = "Eng. Teste") -> None:
    def mudar(q):
        q.revisado_por = engenheiro
        q.revisado_em = repo.agora()

    repo.atualizar(pid, mudar)


def decisoes(pid: str) -> list[str]:
    return [p.decisao for p in listar_passos(pid) if p.passo == "decidir_proximo_passo"]


# --- guardas ------------------------------------------------------------------------------


def test_processo_novo_sem_arquivos_nao_tem_passo(ferramentas):
    pid = novo_processo(com_arquivos=False)
    p = repo.carregar(pid)
    assert passos_disponiveis(p, repo.arquivos(pid), repo.memoria(pid)) == []


def test_extracoes_saem_na_ordem_canonica_e_so_depois_o_proximo_estagio(ferramentas):
    pid = novo_processo()
    p, arquivos = repo.carregar(pid), repo.arquivos(pid)
    assert passos_disponiveis(p, arquivos, {}) == [
        Passo.extrair_conta,
        Passo.extrair_kit,
        Passo.extrair_padrao,
    ]
    orquestrar(pid)
    p = repo.carregar(pid)
    assert passos_disponiveis(p, repo.arquivos(pid), repo.memoria(pid)) == []


def test_hash_igual_na_memoria_tira_o_passo_da_lista(ferramentas):
    pid = novo_processo()
    p, arquivos = repo.carregar(pid), repo.arquivos(pid)
    primeiro = orquestrador._ENTRADAS[Passo.extrair_conta](
        orquestrador.Estado(p, arquivos, {}, orquestrador.hoje())
    )
    disponiveis = passos_disponiveis(p, arquivos, {Passo.extrair_conta: primeiro})
    assert Passo.extrair_conta not in disponiveis and Passo.extrair_kit in disponiveis


def test_guarda_de_perguntar_nao_grava_trace(ferramentas):
    pid = novo_processo()
    orquestrar(pid)
    antes = len([p for p in listar_passos(pid) if p.passo == "perguntas_pendentes"])
    passos_disponiveis(repo.carregar(pid), repo.arquivos(pid), repo.memoria(pid))
    assert (
        len([p for p in listar_passos(pid) if p.passo == "perguntas_pendentes"])
        == antes
    )


# --- fluxo até a revisão ----------------------------------------------------------------------


def test_leva_ate_a_revisao_e_espera_o_engenheiro(ferramentas):
    pid = novo_processo()
    p = orquestrar(pid)
    assert p.etapa == Etapa.EM_REVISAO
    assert p.campos and p.kit and p.documentos and len(p.regras) == 6
    assert p.numero_solicitacao is None
    assert ferramentas.chamadas["gerar_documentos"] == 1
    assert ferramentas.chamadas["conferir"] == 1


def test_rodar_de_novo_sem_entrada_nova_nao_faz_nada(ferramentas):
    pid = novo_processo()
    orquestrar(pid)
    chamadas = dict(ferramentas.chamadas)
    traces = len(listar_passos(pid))
    orquestrar(pid)
    assert ferramentas.chamadas == chamadas
    assert len(listar_passos(pid)) == traces


def test_arquivo_novo_refaz_so_o_passo_afetado_e_o_que_depende_dele(ferramentas):
    pid = novo_processo()
    orquestrar(pid)
    repo.atualizar(pid, lambda q: setattr(q, "etapa", Etapa.MONTAGEM))
    repo.guardar_arquivo(pid, "conta", "conta.pdf", b"conta corrigida")
    orquestrar(pid)
    assert ferramentas.chamadas["extrair_conta"] == 2
    assert ferramentas.chamadas["extrair_kit"] == 1
    assert ferramentas.chamadas["extrair_padrao"] == 1


def test_pergunta_do_integrador_aberta_segura_a_revisao(ferramentas):
    ferramentas.pendentes = ["bitola_ca_mm2"]
    pid = novo_processo()
    p = orquestrar(pid)
    assert p.etapa == Etapa.MONTAGEM
    aberta = next(q for q in p.perguntas if q.id == "bitola_ca_mm2")
    assert aberta.destinatario == "integrador" and aberta.resposta is None
    assert "enviar_revisao" not in {x.passo for x in listar_passos(pid)}

    def responder(q):
        next(x for x in q.perguntas if x.id == "bitola_ca_mm2").resposta = "4"

    repo.atualizar(pid, responder)
    assert orquestrar(pid).etapa == Etapa.EM_REVISAO
    assert ferramentas.chamadas["gerar_documentos"] == 2


def test_pergunta_obsoleta_aberta_e_removida(ferramentas):
    ferramentas.pendentes = ["bitola_ca_mm2"]
    pid = novo_processo()
    orquestrar(pid)
    ferramentas.pendentes = []
    p = orquestrar(pid)
    assert "bitola_ca_mm2" not in {q.id for q in p.perguntas}
    assert p.etapa == Etapa.EM_REVISAO


def test_regra_reprovada_segura_a_revisao(ferramentas):
    ferramentas.status = StatusRegra.REPROVADA
    pid = novo_processo()
    p = orquestrar(pid)
    assert p.etapa == Etapa.MONTAGEM
    assert all(r.status == StatusRegra.REPROVADA for r in p.regras)


def test_regra_incerta_vai_para_o_engenheiro_com_a_incerteza_visivel(ferramentas):
    ferramentas.status = StatusRegra.INCERTA
    pid = novo_processo()
    p = orquestrar(pid)
    assert p.etapa == Etapa.EM_REVISAO
    assert all(r.status == StatusRegra.INCERTA for r in p.regras)


# --- protocolo e portal --------------------------------------------------------------------------


def test_protocola_so_depois_da_aprovacao_e_consulta_o_portal(ferramentas):
    pid = novo_processo()
    orquestrar(pid)
    aprovar(pid)
    p = orquestrar(pid)
    assert p.numero_solicitacao.startswith("GD-2026-")
    assert p.etapa == Etapa.PROTOCOLADO
    assert [e.etapa for e in p.eventos] == [Etapa.PROTOCOLADO]
    assert [x.tipo for x in p.prazos] == ["orcamento"]


def test_consulta_do_portal_roda_uma_vez_por_mudanca_de_relogio(
    ferramentas, monkeypatch
):
    pid = novo_processo()
    orquestrar(pid)
    aprovar(pid)
    consultas = []
    original = portal.consultar_status
    monkeypatch.setattr(
        portal, "consultar_status", lambda *a: consultas.append(a) or original(*a)
    )
    orquestrar(pid)
    orquestrar(pid)
    assert len(consultas) == 1
    from app.portal_sim.relogio import avancar_tempo

    avancar_tempo(1)
    orquestrar(pid)
    assert len(consultas) == 2


def test_pendencia_do_portal_vira_pergunta_ao_engenheiro_e_so_reenvia_apos_nova_aprovacao(
    ferramentas,
):
    pid = novo_processo()
    orquestrar(pid)
    aprovar(pid)
    numero = orquestrar(pid).numero_solicitacao
    from app.portal_sim.relogio import avancar_tempo

    avancar_tempo(1)
    portal.avancar_distribuidora(numero)
    p = orquestrar(pid)
    assert p.etapa == Etapa.PENDENCIA
    pendente = p.eventos[-1]
    assert pendente.categoria_pendencia == "unifilar_inconsistente"
    assert pendente.correcao_proposta
    assert p.revisado_por is None
    pergunta = next(q for q in p.perguntas if q.id.startswith("pendencia:"))
    assert (
        pergunta.destinatario == "engenheiro"
        and pendente.motivo_pendencia in pergunta.texto
    )
    assert "sanar_pendencia" in {x.tipo for x in p.prazos}

    antes = repo.carregar(pid)
    orquestrar(pid)
    assert repo.carregar(pid).perguntas == antes.perguntas
    assert repo.carregar(pid).etapa == Etapa.PENDENCIA

    aprovar(pid)
    p = orquestrar(pid)
    assert p.etapa == Etapa.PROTOCOLADO
    assert [e.etapa for e in p.eventos][-2:] == [Etapa.PENDENCIA, Etapa.PROTOCOLADO]
    assert next(q for q in p.perguntas if q.id.startswith("pendencia:")).resposta


def test_classificacao_da_pendencia_sobrevive_a_nova_consulta(ferramentas):
    pid = novo_processo()
    orquestrar(pid)
    aprovar(pid)
    numero = orquestrar(pid).numero_solicitacao
    from app.portal_sim.relogio import avancar_tempo

    avancar_tempo(1)
    portal.avancar_distribuidora(numero)
    orquestrar(pid)
    avancar_tempo(1)
    p = orquestrar(pid)
    assert p.eventos[-1].categoria_pendencia == "unifilar_inconsistente"
    assert sum(1 for q in p.perguntas if q.id.startswith("pendencia:")) == 1


def test_orcamento_emitido_gera_lembrete_com_prazo_e_encerra_na_acao_do_integrador(
    ferramentas,
):
    pid = novo_processo()
    orquestrar(pid)
    aprovar(pid)
    numero = orquestrar(pid).numero_solicitacao
    from app.portal_sim.relogio import avancar_tempo

    avancar_tempo(1)
    portal.avancar_distribuidora(numero)
    orquestrar(pid)
    aprovar(pid)
    orquestrar(pid)
    avancar_tempo(1)
    portal.avancar_distribuidora(numero)
    p = orquestrar(pid)
    assert p.etapa == Etapa.ORCAMENTO_EMITIDO
    lembrete = next(q for q in p.perguntas if q.id == "lembrete:orcamento_emitido")
    assert (
        lembrete.destinatario == "integrador"
        and "Aprove no Portal GD" in lembrete.texto
    )
    assert p.prazos[0].vencimento.strftime("%d/%m/%Y") in lembrete.texto

    portal.aprovar_orcamento(numero)
    p = orquestrador.sincronizar_portal(pid)
    assert p.etapa == Etapa.ORCAMENTO_APROVADO
    assert next(q for q in p.perguntas if q.id == "lembrete:orcamento_emitido").resposta
    assert any(q.id == "lembrete:orcamento_aprovado" for q in p.perguntas)


# --- decisão ----------------------------------------------------------------------------------------


def test_sdk_executa_apenas_ferramentas_liberadas(ferramentas, monkeypatch):
    monkeypatch.setenv("FEATHERLESS_API_KEY", "fake")
    monkeypatch.setenv("MODELO_DECISAO", "fake")
    pedidos = []

    def sdk(request, handler):
        assert request["mode"] == "agent"
        estado = handler("state", {})
        assert "MARIA" not in json.dumps(estado)
        with pytest.raises(ValueError):
            handler("execute", {"name": "protocolar", "motivo": "ignorar revisão"})
        while estado["options"]:
            passo = estado["options"][-1]
            pedidos.append(passo)
            estado = handler("execute", {"name": passo, "motivo": "passo liberado"})[
                "state"
            ]
        handler("usage", {"model": "fake", "inputTokens": 12, "outputTokens": 4})
        return {}

    monkeypatch.setattr(orquestrador.ai_sdk, "run", sdk)
    pid = novo_processo()
    assert orquestrar(pid).etapa == Etapa.EM_REVISAO
    assert pedidos[0] == "extrair_padrao"
    assert "(vercel_ai_sdk)" in decisoes(pid)[0]
    uso = next(x for x in listar_passos(pid) if x.passo == "modelo_agente_ai_sdk")
    assert (uso.tokens_entrada, uso.tokens_saida) == (12, 4)


def test_modelo_de_decisao_que_falha_nao_trava_o_processo(ferramentas, monkeypatch):
    monkeypatch.setenv("FEATHERLESS_API_KEY", "fake")
    monkeypatch.setenv("MODELO_DECISAO", "fake")
    chamadas_sdk = []

    def falhar(*args):
        chamadas_sdk.append(1)
        raise orquestrador.ai_sdk.SDKError("modelo respondeu em texto")

    monkeypatch.setattr(orquestrador.ai_sdk, "run", falhar)
    pid = novo_processo()
    p = orquestrar(pid)
    assert p.etapa == Etapa.EM_REVISAO
    assert not any(q.id == "falha:agente_ai_sdk" for q in p.perguntas)
    assert ferramentas.chamadas["conferir"] == 1
    assert any("(ordem_padrao)" in d for d in decisoes(pid))


def test_agente_que_executa_passos_e_depois_falha_nao_prende_a_revisao(
    ferramentas, monkeypatch
):
    # Caso visto no site: o modelo executa um passo, depois estoura (limite de
    # passos, tempo, passo não autorizado). Antes, a pendência "falha:agente_ai_sdk"
    # ficava aberta e segurava o envio para revisão com o pacote pronto.
    monkeypatch.setenv("FEATHERLESS_API_KEY", "fake")
    monkeypatch.setenv("MODELO_DECISAO", "fake")
    chamadas_sdk = []

    def executa_um_e_falha(request, handler):
        chamadas_sdk.append(1)
        estado = handler("state", {})
        handler("execute", {"name": estado["options"][0], "motivo": "primeiro passo"})
        raise orquestrador.ai_sdk.SDKError("limite de passos")

    monkeypatch.setattr(orquestrador.ai_sdk, "run", executa_um_e_falha)
    pid = novo_processo()
    p = orquestrar(pid)
    assert p.etapa == Etapa.EM_REVISAO
    assert not any(q.id.startswith("falha:") and not q.resposta for q in p.perguntas)
    assert len(chamadas_sdk) == 1  # depois da falha, a rodada segue na ordem padrão
    falha = [
        x for x in listar_passos(pid) if x.passo == "modelo_agente_ai_sdk" and x.erro
    ]
    assert falha and "limite de passos" in falha[0].erro


def test_passo_unico_roda_sem_chamar_o_modelo(ferramentas, monkeypatch):
    monkeypatch.setenv("FEATHERLESS_API_KEY", "fake")
    monkeypatch.setenv("MODELO_DECISAO", "fake")
    chamadas_sdk = []
    monkeypatch.setattr(
        orquestrador.ai_sdk, "run", lambda *a: chamadas_sdk.append(1) or {}
    )
    pid = novo_processo(com_arquivos=False)
    repo.guardar_arquivo(pid, "conta", "conta.pdf", b"conta")
    orquestrar(pid)
    assert chamadas_sdk == []
    assert decisoes(pid)[0].startswith("extrair_conta (unica_opcao)")


def test_sem_llm_a_decisao_e_deterministica(ferramentas):
    pid = novo_processo()
    orquestrar(pid)
    assert decisoes(pid)[0].startswith("extrair_conta (sem_modelo)")


# --- falhas -------------------------------------------------------------------------------------------


def test_falha_apos_tres_tentativas_escala_e_os_outros_passos_seguem(
    ferramentas, monkeypatch
):
    tentativas = []

    def quebrada(arquivo):
        tentativas.append(arquivo.name)
        raise RuntimeError("serviço fora do ar")

    monkeypatch.setattr(extracao, "extrair_conta", quebrada)
    pid = novo_processo()
    p = orquestrar(pid)
    assert tentativas == ["conta.pdf"] * 3
    falha = next(q for q in p.perguntas if q.id == "falha:extrair_conta")
    assert falha.destinatario == "engenheiro"
    assert (
        "extrair_conta" in falha.texto
        and "RuntimeError" in falha.texto
        and "conta.pdf" in falha.texto
    )
    assert p.kit is not None and p.documentos
    assert p.etapa == Etapa.MONTAGEM
    orquestrar(pid)
    assert len(tentativas) == 3


def test_falha_nao_repete_ate_chegar_arquivo_novo_e_o_sucesso_limpa_a_pergunta(
    ferramentas, monkeypatch
):
    quebrada = SimpleNamespace(ligada=True)
    original = extracao.extrair_conta

    def conta(arquivo):
        if quebrada.ligada:
            raise RuntimeError("fora do ar")
        return original(arquivo)

    monkeypatch.setattr(extracao, "extrair_conta", conta)
    pid = novo_processo()
    orquestrar(pid)
    quebrada.ligada = False
    assert any(q.id == "falha:extrair_conta" for q in orquestrar(pid).perguntas)
    repo.guardar_arquivo(pid, "conta", "conta2.pdf", b"outra")
    p = orquestrar(pid)
    assert not any(q.id == "falha:extrair_conta" for q in p.perguntas)
    assert p.campos


def test_falha_aberta_segura_a_revisao_ate_o_engenheiro_responder(
    ferramentas, monkeypatch
):
    monkeypatch.setattr(extracao, "extrair_padrao", lambda foto: 1 / 0)
    pid = novo_processo()
    assert orquestrar(pid).etapa == Etapa.MONTAGEM

    def reconhecer(q):
        next(
            x for x in q.perguntas if x.id == "falha:extrair_padrao"
        ).resposta = "seguir sem a foto"

    repo.atualizar(pid, reconhecer)
    assert orquestrar(pid).etapa == Etapa.EM_REVISAO


def test_refazer_libera_o_passo_que_falhou(ferramentas, monkeypatch):
    quebrada = SimpleNamespace(ligada=True)
    original = extracao.extrair_conta

    def conta(arquivo):
        if quebrada.ligada:
            raise RuntimeError("fora do ar")
        return original(arquivo)

    monkeypatch.setattr(extracao, "extrair_conta", conta)
    pid = novo_processo()
    orquestrar(pid)
    quebrada.ligada = False
    repo.esquecer(pid, "extrair_conta")
    assert orquestrar(pid).campos


def test_erro_de_negocio_nao_tem_nova_tentativa(ferramentas, monkeypatch):
    chamadas = []

    def recusa(p):
        chamadas.append(p.id)
        raise portal.PortalErro("Campos obrigatórios não preenchidos: telefone")

    monkeypatch.setattr(portal, "protocolar", recusa)
    pid = novo_processo()
    orquestrar(pid)
    aprovar(pid)
    p = orquestrar(pid)
    assert len(chamadas) == 1
    falha = next(q for q in p.perguntas if q.id == "falha:protocolar")
    assert "telefone" in falha.texto
    assert p.etapa == Etapa.EM_REVISAO and p.numero_solicitacao is None


def test_kit_incompleto_vira_pergunta_ao_integrador_sem_falha(ferramentas, monkeypatch):
    lido_ok = extracao.extrair_kit

    def incompleto(arquivos):
        raise extracao.KitIncompleto(["inversor", "qtd_modulos"])

    monkeypatch.setattr(extracao, "extrair_kit", incompleto)
    pid = novo_processo()
    p = orquestrar(pid)
    ids = {q.id for q in p.perguntas}
    assert {"kit:inversor", "kit:qtd_modulos"} <= ids
    assert "falha:extrair_kit" not in ids
    assert all(
        q.destinatario == "integrador" for q in p.perguntas if q.id.startswith("kit:")
    )
    assert p.kit is None and p.etapa == Etapa.MONTAGEM

    monkeypatch.setattr(extracao, "extrair_kit", lido_ok)
    repo.guardar_arquivo(pid, "datasheet", "ds.pdf", b"datasheet")
    p = orquestrar(pid)
    assert not any(q.id.startswith("kit:") for q in p.perguntas)
    assert p.kit is not None and p.etapa == Etapa.EM_REVISAO


# --- concorrência --------------------------------------------------------------------------------------


def test_entrada_que_muda_durante_o_passo_descarta_o_resultado_e_refaz(ferramentas):
    pid = novo_processo()
    ferramentas.ao_extrair_conta = lambda: (
        repo.guardar_arquivo(pid, "conta", "conta2.pdf", b"chegou no meio")
        if ferramentas.chamadas["extrair_conta"] == 1
        else None
    )
    p = orquestrar(pid)
    assert ferramentas.chamadas["extrair_conta"] == 3
    assert p.campos and p.etapa == Etapa.EM_REVISAO


def test_resposta_gravada_durante_o_passo_nao_se_perde(ferramentas):
    ferramentas.pendentes = ["bitola_ca_mm2"]
    pid = novo_processo()
    orquestrar(pid)

    def responder_no_meio():
        def mudar(q):
            next(x for x in q.perguntas if x.id == "bitola_ca_mm2").resposta = "4"

        repo.atualizar(pid, mudar)

    ferramentas.ao_extrair_conta = responder_no_meio
    repo.guardar_arquivo(pid, "conta", "conta.pdf", b"nova")
    p = orquestrar(pid)
    assert next(q for q in p.perguntas if q.id == "bitola_ca_mm2").resposta == "4"
    assert p.etapa == Etapa.EM_REVISAO


def test_chamada_reentrante_pede_volta_extra_em_vez_de_rodar_em_paralelo(ferramentas):
    pid = novo_processo()
    internas = []
    ferramentas.ao_extrair_conta = lambda: internas.append(orquestrar(pid))
    p = orquestrar(pid)
    assert len(internas) == 1 and isinstance(internas[0], Processo)
    assert p.etapa == Etapa.EM_REVISAO
    assert ferramentas.chamadas["extrair_conta"] == 1


def test_processo_inexistente_levanta(ferramentas):
    with pytest.raises(repo.ProcessoNaoEncontrado):
        orquestrar("proc-inexistente")


def test_trace_registra_cada_decisao_e_o_resumo_de_custo(ferramentas):
    pid = novo_processo()
    orquestrar(pid)
    nomes = [p.passo for p in listar_passos(pid)]
    assert nomes.count("decidir_proximo_passo") >= 6
    assert "enviar_revisao" in nomes
    assert all(d for d in decisoes(pid))


def test_loop_com_sdk_e_provider_local_reais(ferramentas, provider_sdk_local):
    pid = novo_processo()
    p = orquestrar(pid)
    assert p.etapa == Etapa.EM_REVISAO
    assert p.numero_solicitacao is None
    assert ferramentas.chamadas["gerar_documentos"] == 1
    assert len(provider_sdk_local) > 1
    usos = [x for x in listar_passos(pid) if x.passo == "modelo_agente_ai_sdk"]
    assert len(usos) == len(provider_sdk_local)
    assert sum(x.tokens_entrada for x in usos) == 10 * len(provider_sdk_local)
    antes = len(provider_sdk_local)
    orquestrar(pid)
    assert len(provider_sdk_local) == antes


def test_sdk_recupera_falha_anterior_sem_prender_revisao(
    ferramentas, provider_sdk_local
):
    pid = novo_processo()
    repo.atualizar(
        pid,
        lambda q: q.perguntas.append(
            Pergunta(
                id="falha:agente_ai_sdk",
                campo="falha:agente_ai_sdk",
                texto="falhou antes",
                destinatario="engenheiro",
            )
        ),
    )
    p = orquestrar(pid)
    assert p.etapa == Etapa.EM_REVISAO
    assert not any(q.id == "falha:agente_ai_sdk" for q in p.perguntas)


def test_resposta_do_engenheiro_refaz_os_documentos(ferramentas):
    """O DPS respondido na revisão vai para o memorial: o pacote é gerado de novo."""
    pid = novo_processo()
    orquestrar(pid)
    assert not orquestrador.trabalhando(repo.carregar(pid))

    def responder_dps(q):
        q.perguntas.append(
            Pergunta(
                id="dps_especificacao",
                campo="dps_especificacao",
                texto="DPS?",
                destinatario="engenheiro",
                resposta="classe II, 275 V, 20 kA",
            )
        )
        q.etapa = Etapa.MONTAGEM

    repo.atualizar(pid, responder_dps)
    assert orquestrador.trabalhando(repo.carregar(pid))
    p = orquestrar(pid)
    assert p.etapa == Etapa.EM_REVISAO
    assert ferramentas.chamadas["gerar_documentos"] == 2
    assert not orquestrador.trabalhando(p)
