"""GET /saude: o que o servidor publicado está rodando, sem mostrar segredos.

Serve para conferir o deploy sem acesso ao painel do Render: commit publicado,
se a IA tem chave e modelo (só sim/não e o nome do modelo, nunca a chave),
se o Node e os pacotes do agente (npm ci) estão instalados, e onde fica o banco.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter

RAIZ = Path(__file__).resolve().parents[2]
router = APIRouter()


def _versao_node() -> str | None:
    node = shutil.which("node")
    if node is None:
        return None
    try:
        saida = subprocess.run(
            [node, "--version"], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return saida.stdout.strip() or None


def diagnostico() -> dict:
    from app.core import llm

    pacotes = {
        nome: (RAIZ / "node_modules" / nome / "package.json").is_file()
        for nome in ("ai", "@ai-sdk/openai-compatible", "zod")
    }
    versao = _versao_node()
    principal = os.environ.get("MODELO_PRINCIPAL") or None
    papeis = {
        papel: llm.disponivel(papel) for papel in ("extracao", "decisao", "pendencia")
    }
    problemas = []
    if not os.environ.get("FEATHERLESS_API_KEY"):
        problemas.append("FEATHERLESS_API_KEY não definida")
    if not principal and not os.environ.get("MODELO_EXTRACAO"):
        problemas.append("MODELO_PRINCIPAL não definido")
    if versao is None:
        problemas.append("Node não encontrado no servidor")
    elif int(versao.lstrip("v").split(".")[0]) < 22:
        problemas.append(f"Node {versao}: o agente pede 22 ou mais")
    if not all(pacotes.values()):
        problemas.append(
            "pacotes do agente ausentes: o build precisa rodar 'npm ci --omit=dev'"
        )
    return {
        "ok": not problemas,
        "problemas": problemas,
        "commit": (os.environ.get("RENDER_GIT_COMMIT") or "")[:7] or None,
        "ia": {
            "chave_definida": bool(os.environ.get("FEATHERLESS_API_KEY")),
            "modelo_principal": principal,
            "modelo_fallback": os.environ.get("MODELO_FALLBACK") or None,
            "papeis_disponiveis": papeis,
        },
        "node": {"versao": versao, "pacotes_do_agente": pacotes},
        "banco": "turso" if os.environ.get("TURSO_DATABASE_URL") else os.environ.get("DB_PATH", "data/app.db"),
    }


@router.get("/saude")
def saude() -> dict:
    return diagnostico()
