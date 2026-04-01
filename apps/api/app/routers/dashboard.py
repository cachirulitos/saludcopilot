import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
logger = logging.getLogger(__name__)

_connections: dict[str, list[WebSocket]] = {}


@router.websocket("/ws/dashboard/{clinic_id}")
async def dashboard_websocket(websocket: WebSocket, clinic_id: str):
    """Accept a WebSocket connection and keep it alive for real-time dashboard events."""
    await websocket.accept()
    _connections.setdefault(clinic_id, []).append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _connections[clinic_id].remove(websocket)
        if not _connections[clinic_id]:
            del _connections[clinic_id]


async def broadcast_to_clinic(clinic_id: str, event: dict) -> None:
    """Send an event to all WebSocket connections for a given clinic."""
    active_connections = _connections.get(clinic_id, [])
    dead_connections: list[WebSocket] = []
    for connection in active_connections:
        try:
            await connection.send_json(event)
        except Exception:
            logger.warning("Removing dead WebSocket for clinic %s", clinic_id)
            dead_connections.append(connection)
    for connection in dead_connections:
        active_connections.remove(connection)
    if clinic_id in _connections and not _connections[clinic_id]:
        del _connections[clinic_id]
