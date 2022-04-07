from typing import Optional, Callable, Any
import logging

from fastapi import FastAPI, WebSocket
from fastapi.exceptions import HTTPException
from starlette import status
from starlette.endpoints import WebSocketEndpoint
from pydantic import BaseModel, ValidationError

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

class WebsocketMessage(BaseModel):
    type: str
    data: Any

@app.websocket_route("/ws/{client_id:int}")
class WSApp(WebSocketEndpoint):
    encoding = 'json'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.handlers = {}
        # register all methods starting with on_ as handlers
        for methodname in dir(self):
            if methodname.startswith('on_') and methodname not in ['on_connect', 'on_receive', 'on_disconnect']:
                method = getattr(self, methodname)
                assert callable(method), 'handler methods starting with on_ have to be callable'
                self.set_handler(methodname[3:], getattr(self, methodname))


    def set_handler(self, event: str, method: Callable) -> None:
        """Set a handler for event"""
        #TODO build enum for validation
        if event in ['connect', 'disconnect', 'receive']:
            raise ValueError(f'{event} is reserved')
        elif method == None:
            del self.handlers[event]
            logging.debug(f'Clearing handler for {event}')
        elif event in self.handlers:
            logging.warning(f"Overwriting handler for {event} with {method}")
        else:
            self.handlers[event] = method

    async def on_connect(self, websocket):
        self.client_id = websocket.path_params['client_id']
        await manager.connect(websocket)
        await manager.broadcast(f"#{self.client_id} joined")

    async def on_receive(self, websocket, data):
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
                # validate response
                if isinstance(response, Broadcast):
                    manager.broadcast()


    async def on_disconnect(self, websocket, close_code):
        manager.disconnect(websocket)
        await manager.broadcast(f'Client #{self.client_id} left the chat')

    async def on_message(self, websocket, data):
        await manager.broadcast(f"#{self.client_id}: " + data)

async def send_exception(websocket, exc):
    if isinstance(exc, ValidationError):
        errors = exc.errors()
    elif isinstance(exc, HTTPException):
        errors = [{'msg': exc.detail, 'status_code': exc.status_code, 'type': type(exc).__name__}]
    #elif isinstance(exc, WebsocketException):
        #TODO
    else:
        errors = [{'msg': str(exc), 'type': type(exc).__name__}]

    await websocket.send_json({'errors': errors})
