from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List
import json

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, workspace_id: str, ws: WebSocket):
        await ws.accept()
        self.connections.setdefault(workspace_id, []).append(ws)

    def disconnect(self, workspace_id: str, ws: WebSocket):
        if workspace_id in self.connections:
            try:
                self.connections[workspace_id].remove(ws)
            except ValueError:
                pass

    async def broadcast(self, workspace_id: str, event: dict):
        dead = []
        for ws in self.connections.get(workspace_id, []):
            try:
                await ws.send_text(json.dumps(event))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(workspace_id, ws)

manager = ConnectionManager()


async def notify_user_ws(workspace_id: str, user_id: str):
    """
    Push a notification.new event to all workspace WebSocket clients.
    The frontend filters by user_id so only the target user's bell updates.
    workspace_id: the workspace the notification belongs to (routes to correct WS channel)
    user_id: the recipient — frontend uses this to filter
    """
    await manager.broadcast(workspace_id, {
        "type": "notification.new",
        "user_id": user_id,
    })


async def broadcast_agent_event(workspace_id: str, event_type: str, data: dict):
    """
    Broadcast an agent activity event to all connected workspace clients.
    Called from MCP tool handlers to stream real-time tool activity.

    event_type: "tool_call" | "tool_result" | "tool_error"
    data: {"tool": "lno_list_tasks", "status": "done", "summary": "..."}
    """
    await manager.broadcast(workspace_id, {
        "type": f"agent:{event_type}",
        **data,
    })


@router.websocket("/ws/{workspace_id}")
async def ws_endpoint(workspace_id: str, websocket: WebSocket):
    await manager.connect(workspace_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(workspace_id, json.loads(data))
    except WebSocketDisconnect:
        manager.disconnect(workspace_id, websocket)
