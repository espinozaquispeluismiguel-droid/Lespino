"""Fase 5: canal WebSocket del dashboard de supervisión.

Cliente JS:
    const ws = new WebSocket(`wss://host/ws/layouts/${idLayout}?token=${jwt}`);
    ws.onmessage = (e) => { const {evento, data} = JSON.parse(e.data); ... };
(Los navegadores no permiten cabeceras en WebSocket, por eso el JWT va en query.)
"""
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from fastapi import HTTPException

from app.api.deps import usuario_desde_token
from app.core.database import SessionLocal
from app.models import Layout, RolUsuario
from app.services.inventario_service import calcular_avance_layout
from app.websockets.manager import canal_layout, manager

router = APIRouter(tags=["Tiempo real"])


@router.websocket("/ws/layouts/{id_layout}")
async def ws_layout(websocket: WebSocket, id_layout: int, token: str = Query(...)):
    async with SessionLocal() as db:
        try:
            usuario = await usuario_desde_token(token, db)
        except HTTPException:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        if usuario.rol not in (RolUsuario.ADMINISTRADOR, RolUsuario.SUPERVISOR):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        layout = await db.get(Layout, id_layout)
        if layout is None or layout.id_delegacion != usuario.id_delegacion:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        avance = await calcular_avance_layout(db, id_layout)

    canal = canal_layout(id_layout)
    await manager.connect(canal, websocket)
    # Estado inicial para pintar el dashboard sin otra petición
    await websocket.send_json({"evento": "snapshot", "data": {"avance": avance.model_dump()}})
    try:
        while True:
            msg = await websocket.receive_text()  # keep-alive del cliente
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(canal, websocket)
