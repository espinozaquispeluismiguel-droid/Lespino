"""Gestor de conexiones WebSocket por canal (un canal por layout).

Implementación en memoria: válida con UN proceso uvicorn. Para varios workers o
varias réplicas, sustituir `broadcast` por publicación en Redis Pub/Sub
(o PostgreSQL LISTEN/NOTIFY) y que cada worker reenvíe a sus sockets locales.
"""
import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import WebSocket

log = logging.getLogger(__name__)


def _default(o: Any):
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, datetime):
        return o.isoformat()
    if hasattr(o, "value"):  # Enum
        return o.value
    raise TypeError(f"No serializable: {type(o)}")


class ConnectionManager:
    def __init__(self) -> None:
        self._canales: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, canal: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._canales[canal].add(ws)

    async def disconnect(self, canal: str, ws: WebSocket) -> None:
        async with self._lock:
            self._canales[canal].discard(ws)
            if not self._canales[canal]:
                self._canales.pop(canal, None)

    async def broadcast(self, canal: str, evento: str, data: dict) -> None:
        mensaje = json.dumps({"evento": evento, "data": data}, default=_default)
        async with self._lock:
            destinos = list(self._canales.get(canal, ()))
        muertos = []
        for ws in destinos:
            try:
                await ws.send_text(mensaje)
            except Exception:  # cliente desconectado sin cerrar
                muertos.append(ws)
        for ws in muertos:
            await self.disconnect(canal, ws)

    def conexiones(self, canal: str) -> int:
        return len(self._canales.get(canal, ()))


manager = ConnectionManager()


def canal_layout(id_layout: int) -> str:
    return f"layout:{id_layout}"
