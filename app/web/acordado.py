"""Mantém o site acordado no plano grátis do Render.

O plano grátis desliga o serviço depois de 15 minutos sem acesso e, ao religar,
o disco volta vazio: processos criados no ensaio somem. O próprio app acessa a
sua URL pública a cada 10 minutos; o acesso passa pelo Render e conta como uso.
Só liga no Render (RENDER_EXTERNAL_URL definida) e pode ser desligado com
MANTER_ACORDADO=0.
"""

from __future__ import annotations

import asyncio
import logging
import os
import urllib.request

INTERVALO_S = 10 * 60
log = logging.getLogger(__name__)


def url_publica() -> str | None:
    if os.environ.get("MANTER_ACORDADO", "1") == "0":
        return None
    base = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    return f"{base}/saude" if base else None


def _cutucar(url: str) -> None:
    with urllib.request.urlopen(url, timeout=30) as r:
        r.read(1)


async def manter_acordado(url: str) -> None:
    while True:
        await asyncio.sleep(INTERVALO_S)
        try:
            await asyncio.to_thread(_cutucar, url)
        except Exception as exc:  # noqa: BLE001 - um acesso perdido não derruba nada
            log.warning("Acesso para manter o site acordado falhou: %s", exc)
