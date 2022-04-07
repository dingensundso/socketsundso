from typing import Callable, Any, Dict, List, TYPE_CHECKING
import logging

from fastapi import FastAPI, WebSocket
from fastapi.exceptions import HTTPException
from starlette import status
from pydantic import BaseModel, ValidationError
if TYPE_CHECKING:
    from pydantic.error_wrappers import ErrorDict

from wshandler.endpoints import WebSocketEndpoint

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

class WebSocketHandlingEndpoint(WebSocketEndpoint):
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
            logging.debug('Clearing handler for %s', event)
        elif event in self.handlers:
            logging.warning("Overwriting handler for %s with %s", event, method)
        else:
            self.handlers[event] = method

    async def on_receive(self, data: Any) -> None:
        try:
            msg = WebsocketMessage(**data)
        except ValidationError as exc:
            return await self.send_exception(exc)

        if msg.type not in self.handlers:
            raise RuntimeError(f'invalid event "{msg.type}"')

        logging.debug("Handler called for %s with %s", msg.type, msg.data)
        # todo validate incoming data
        try:
            response = await self.handlers[msg.type](msg.data)
        except HTTPException as exc: #TODO also accept WebsocketException
            await self.send_exception(exc)
        except Exception as exc:
            #TODO remove this! don't send all exceptions to clients
            await self.send_exception(exc)
            await self.websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            raise exc

        if response is not None:
            #TODO validate response
            self.websocket.send_json(response)

    async def send_exception(self, exc: Exception) -> None:
        errors: List[Dict[str,Any]] | List[ErrorDict]
        if isinstance(exc, ValidationError):
            errors = exc.errors()
        elif isinstance(exc, HTTPException):
            errors = [{'msg': exc.detail, 'status_code': exc.status_code, 'type': type(exc).__name__}]
        #elif isinstance(exc, WebsocketException):
            #TODO
        else:
            errors = [{'msg': str(exc), 'type': type(exc).__name__}]

        await self.websocket.send_json({'errors': errors})

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
