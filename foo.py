from typing import Callable, Any, Dict, List, TYPE_CHECKING
import logging

from fastapi import FastAPI, WebSocket
from fastapi.exceptions import HTTPException
from starlette import status

from wshandler.endpoints import WebSocketHandlingEndpoint

app = FastAPI()

class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        await websocket.send_text(message)

    async def broadcast(self, message: str) -> None:
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.websocket_route("/ws/{client_id:int}")
class MyWSApp(WebSocketHandlingEndpoint):
    client_id = None

    async def on_connect(self) -> None:
        self.client_id = self.websocket.path_params['client_id']
        await manager.connect(self.websocket)
        await manager.broadcast(f"#{self.client_id} joined")

    async def on_disconnect(self, close_code: int) -> None:
        manager.disconnect(self.websocket)
        await manager.broadcast(f'Client #{self.client_id} left the chat')

    async def on_message(self, data: str) -> None:
        await manager.broadcast(f"#{self.client_id}: " + data)
