from pathlib import Path

import pytest

from app.docs.gerar import gerar_documentos
from app.schemas import Processo

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


@pytest.fixture(autouse=True)
def ambiente_temporario(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "teste.db"))
    monkeypatch.setenv("DOCS_DIR", str(tmp_path / "docs"))
    monkeypatch.setenv("RELOGIO_INICIO", "2026-11-09")
    for nome in ("LLM_PRECO_ENTRADA_USD_MTOK", "LLM_PRECO_SAIDA_USD_MTOK", "USD_BRL"):
        monkeypatch.delenv(nome, raising=False)


def _carregar(nome: str) -> Processo:
    return Processo.model_validate_json((FIXTURES / nome).read_text())


@pytest.fixture
def processo() -> Processo:
    return _carregar("processo_exemplo.json")


@pytest.fixture
def protocolado() -> Processo:
    return _carregar("processo_protocolado.json")


@pytest.fixture
def confirmado(processo: Processo) -> Processo:
    """Exemplo com strings confirmadas, cabo informado e disjuntor CA de 25 A.

    Cabo de 6 mm²: pelo parecer (R02, Iz corrigido em B2, 35 °C, 2 circuitos),
    o disjuntor de 25 A pede 6 mm²; 4 mm² (22,6 A) reprova. Área de concessão
    informada para a R03 ter a temperatura mínima."""
    for s in processo.kit.strings:
        s.sugerida = False
    processo.visita.bitola_ca_mm2 = 6
    processo.visita.area_concessao = "ceara"
    return processo


@pytest.fixture
def com_documentos(confirmado: Processo) -> Processo:
    confirmado.documentos = gerar_documentos(confirmado)
    return confirmado


@pytest.fixture
def provider_sdk_local(monkeypatch):
    """API compatível simulada: exercita Node/AI SDK reais sem sair da máquina."""
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(request)
            tools = request.get("tools", [])
            message = {"role": "assistant", "content": '{"nome":"Ana","idade":30}'}
            if tools:
                message = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": f"call-{len(requests)}",
                            "type": "function",
                            "function": {
                                "name": tools[0]["function"]["name"],
                                "arguments": '{"motivo":"passo disponível"}',
                            },
                        }
                    ],
                }
            body = json.dumps(
                {
                    "id": "local",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "local",
                    "choices": [
                        {
                            "index": 0,
                            "message": message,
                            "finish_reason": "tool_calls" if tools else "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "total_tokens": 15,
                    },
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    monkeypatch.setenv("FEATHERLESS_API_KEY", "fake-local")
    monkeypatch.setenv(
        "FEATHERLESS_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1"
    )
    monkeypatch.setenv("MODELO_PRINCIPAL", "local")
    monkeypatch.delenv("MODELO_FALLBACK", raising=False)
    try:
        yield requests
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
