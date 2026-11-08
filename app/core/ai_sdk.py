"""Ponte privada por stdin/stdout: AI SDK em Node, ferramentas no processo Python.

Não expõe endpoints de execução nem credenciais em argumentos de comando.
"""

from __future__ import annotations

import json
import selectors
import subprocess
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "agent" / "worker.mjs"
# A Featherless levou 69 s numa extração de kit medida; 90 s cortava chamadas válidas.
SEM_RESPOSTA_S = 180


class SDKError(Exception):
    pass


def run(request: dict, handler: Callable | None = None) -> dict:
    try:
        process = subprocess.Popen(
            ["node", str(WORKER)],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
    except OSError as error:
        raise SDKError(
            "Node.js indisponível; instale Node >=22 e execute npm ci"
        ) from error
    try:
        assert process.stdin and process.stdout
        process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
        process.stdin.flush()
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                if not selector.select(timeout=SEM_RESPOSTA_S):
                    raise SDKError(f"AI SDK sem resposta por {SEM_RESPOSTA_S} segundos")
                line = process.stdout.readline()
                if not line:
                    raise SDKError(
                        "AI SDK encerrou sem resultado; confira npm ci e Node >=22"
                    )
                message = json.loads(line)
                if message["type"] == "error":
                    raise SDKError(message["error"])
                if message["type"] == "result":
                    return message["result"]
                if message["type"] != "request" or handler is None:
                    raise SDKError("Mensagem inesperada do AI SDK")
                try:
                    response = {
                        "id": message["id"],
                        "result": handler(message["method"], message["params"]),
                    }
                except Exception:  # noqa: BLE001 - erro sanitizado para o modelo
                    response = {"id": message["id"], "error": "Ferramenta recusada"}
                process.stdin.write(json.dumps(response, ensure_ascii=False) + "\n")
                process.stdin.flush()
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        if process.stdin:
            process.stdin.close()
        if process.stdout:
            process.stdout.close()
