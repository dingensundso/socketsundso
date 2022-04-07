from typing import Optional, Callable, Any, Dict, List
import logging

from fastapi import FastAPI, WebSocket
from fastapi.exceptions import HTTPException
from starlette import status
from starlette.endpoints import WebSocketEndpoint
from pydantic import BaseModel, ValidationError
from pydantic.error_wrappers import ErrorDict

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

class WebsocketMessage(BaseModel):
    type: str
    data: Any

class WSApp(WebSocketEndpoint):
    encoding = 'json'

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.handlers: Dict[str, Callable] = {}
        # register all methods starting with on_ as handlers
        for methodname in dir(self):
            if methodname.startswith('on_') and methodname not in ['on_connect', 'on_receive', 'on_disconnect']:
                method = getattr(self, methodname)
                assert callable(method), 'handler methods starting with on_ have to be callable'
                self.set_handler(methodname[3:], getattr(self, methodname))

    def set_handler(self, event: str, method: Callable) -> None:
        """Set a handler for event"""
        #TODO build enum for validation
        assert event not in ['connect', 'disconnect', 'receive'], f'{event} is reserved'
        if method is None:
            del self.handlers[event]
            logging.debug(f'Clearing handler for {event}')
        elif event in self.handlers:
            logging.warning(f"Overwriting handler for {event} with {method}")
        else:
            self.handlers[event] = method

    async def on_receive(self, websocket: WebSocket, data: Any) -> None:
        try:
            msg = WebsocketMessage(**data)
        except ValidationError as e:
            return await send_exception(websocket, e)

        if msg.type not in self.handlers:
            raise RuntimeError(f'invalid event "{msg.type}"')
        else:
            logging.debug(f"Handler called for {msg.type=} with {msg.data=}")
            # todo validate incoming data
            try:
                response = await self.handlers[msg.type](websocket, msg.data)
            except HTTPException as e: #TODO also accept WebsocketException
                await send_exception(websocket, e)
            except Exception as e:
                #TODO remove this! don't send all exceptions to clients
                await send_exception(websocket, e)
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
                raise e

            if response is not None:
                #TODO validate response
                websocket.send_json(response)

async def send_exception(websocket: WebSocket, exc: Exception) -> None:
    errors: List[Dict[str,Any]] | List[ErrorDict]
    if isinstance(exc, ValidationError):
        errors = exc.errors()
    elif isinstance(exc, HTTPException):
        errors = [{'msg': exc.detail, 'status_code': exc.status_code, 'type': type(exc).__name__}]
    #elif isinstance(exc, WebsocketException):
        #TODO
    else:
        errors = [{'msg': str(exc), 'type': type(exc).__name__}]

    await websocket.send_json({'errors': errors})

manager = ConnectionManager()

@app.websocket_route("/ws/{client_id:int}")
class MyWSApp(WSApp):
    async def on_connect(self, websocket: WebSocket) -> None:
        self.client_id = websocket.path_params['client_id']
        await manager.connect(websocket)
        await manager.broadcast(f"#{self.client_id} joined")

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        manager.disconnect(websocket)
        await manager.broadcast(f'Client #{self.client_id} left the chat')

    async def on_message(self, websocket: WebSocket, data: str) -> None:
        await manager.broadcast(f"#{self.client_id}: " + data)
