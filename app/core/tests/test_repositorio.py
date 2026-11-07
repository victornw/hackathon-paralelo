import threading

import pytest

from app.core import repositorio as repo
from app.schemas import Etapa, Pergunta


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("RELOGIO_INICIO", "2026-11-09")


def test_criar_gera_id_e_data_do_relogio_simulado():
    p = repo.criar("a@b.com")
    assert p.id.startswith("proc-") and len(p.id) == len("proc-") + 8
    assert p.criado_em.date().isoformat() == "2026-11-09"
    assert p.etapa == Etapa.MONTAGEM
    assert p.email_contato == "a@b.com"


def test_salvar_carregar_e_listar_em_ordem_de_criacao():
    a, b = repo.criar(), repo.criar()
    a.etapa = Etapa.EM_REVISAO
    repo.salvar(a)
    assert repo.carregar(a.id).etapa == Etapa.EM_REVISAO
    assert [p.id for p in repo.listar()] == [a.id, b.id]


def test_carregar_inexistente_levanta():
    with pytest.raises(repo.ProcessoNaoEncontrado):
        repo.carregar("proc-nao-existe")


def test_atualizar_nao_salva_quando_a_mudanca_levanta():
    p = repo.criar()

    def mudar(q):
        q.etapa = Etapa.CONCLUIDO
        raise RuntimeError("falhou no meio")

    with pytest.raises(RuntimeError):
        repo.atualizar(p.id, mudar)
    assert repo.carregar(p.id).etapa == Etapa.MONTAGEM


def test_atualizar_concorrente_nao_perde_escritas():
    p = repo.criar()

    def adicionar(i):
        repo.atualizar(
            p.id,
            lambda q: q.perguntas.append(Pergunta(id=f"q{i}", campo="x", texto="?")),
        )

    threads = [threading.Thread(target=adicionar, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(repo.carregar(p.id).perguntas) == 20


def test_uploads_ficam_por_processo_e_tipo():
    p = repo.criar()
    caminho = repo.guardar_arquivo(p.id, "conta", "../../conta.pdf", b"abc")
    assert caminho.parent.name == "conta" and caminho.parent.parent.name == p.id
    assert caminho.name == "conta.pdf" and caminho.read_bytes() == b"abc"
    repo.guardar_arquivo(p.id, "padrao", "foto.jpg", b"x")
    achados = repo.arquivos(p.id)
    assert [a.name for a in achados["conta"]] == ["conta.pdf"]
    assert [a.name for a in achados["padrao"]] == ["foto.jpg"]
    assert achados["proposta"] == [] and achados["datasheet"] == []


def test_upload_com_tipo_ou_nome_invalido():
    p = repo.criar()
    with pytest.raises(ValueError):
        repo.guardar_arquivo(p.id, "outro", "a.pdf", b"")
    with pytest.raises(ValueError):
        repo.guardar_arquivo(p.id, "conta", "..", b"")


def test_memoria_marcar_sobrescrever_e_esquecer():
    p = repo.criar()
    assert repo.memoria(p.id) == {}
    repo.marcar(p.id, "conferir", "h1")
    repo.marcar(p.id, "conferir", "h2")
    repo.marcar(p.id, "extrair_conta", "h3")
    assert repo.memoria(p.id) == {"conferir": "h2", "extrair_conta": "h3"}
    repo.esquecer(p.id, "conferir")
    assert repo.memoria(p.id) == {"extrair_conta": "h3"}
