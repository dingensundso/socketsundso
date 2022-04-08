import typing
import json
import logging

from starlette import status
from starlette.types import Message, Receive, Scope, Send
from starlette.exceptions import HTTPException
from starlette.websockets import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError
if typing.TYPE_CHECKING:
    from pydantic.error_wrappers import ErrorDict

class WebsocketEventMessage(BaseModel):
    type: str
    data: typing.Any

class WebSocketHandlingEndpoint:
    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "websocket"
        self.scope = scope
        self.receive = receive
        self.send = send
        self.websocket = WebSocket(self.scope, receive=self.receive, send=self.send)
        self.handlers: typing.Dict[str, typing.Callable] = {}

        # register all methods starting with on_ as handlers
        for methodname in dir(self):
            if methodname.startswith('on_') and methodname not in ['on_connect', 'on_receive', 'on_disconnect']:
                method = getattr(self, methodname)
                assert callable(method), 'handler methods starting with on_ have to be callable'
                self.set_handler(methodname[3:], getattr(self, methodname))

    def __await__(self) -> typing.Generator:
        return self.dispatch().__await__()

    def set_handler(self, event: str, method: typing.Callable) -> None:
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

    async def dispatch(self) -> None:
        await self.on_connect()

        close_code = status.WS_1000_NORMAL_CLOSURE

        try:
            while True:
                try:
                    data = await self.websocket.receive_json()
                    msg = WebsocketEventMessage(**data)
                except json.decoder.JSONDecodeError:
                    await self.websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                    raise RuntimeError("Malformed JSON data received.")
                except ValidationError as exc:
                    await self.send_exception(exc)
                except WebSocketDisconnect as exc:
                    close_code = exc.code

                try:
                    await self.handle(msg)
                except WebSocketDisconnect as exc:
                    close_code = exc.code
                except HTTPException as exc: #TODO also accept WebsocketException
                    await self.send_exception(exc)
                #TODO remove this! don't send all exceptions to clients
                except Exception as exc:
                    await self.send_exception(exc)
                    raise exc

        except Exception as exc:
            close_code = status.WS_1011_INTERNAL_ERROR
            raise exc
        finally:
            await self.on_disconnect(close_code)

    async def handle(self, msg: WebsocketEventMessage) -> None:
        if msg.type not in self.handlers:
            raise RuntimeError(f'invalid event "{msg.type}"')

        logging.debug("Handler called for %s with %s", msg.type, msg.data)

        # todo validate incoming data
        response = await self.handlers[msg.type](msg.data)

        if response is not None:
            #TODO validate response
            self.send_json(response)

    async def send_json(self, response: typing.Any) -> None:
        return await self.websocket.send_json(response)

    async def send_exception(self, exc: Exception) -> None:
        errors: typing.List[typing.Dict[str,typing.Any]] | typing.List[ErrorDict]
        if isinstance(exc, ValidationError):
            errors = exc.errors()
        elif isinstance(exc, HTTPException):
            errors = [{'msg': exc.detail, 'status_code': exc.status_code, 'type': type(exc).__name__}]
        #elif isinstance(exc, WebsocketException):
            #TODO
        else:
            errors = [{'msg': str(exc), 'type': type(exc).__name__}]

        await self.send_json({'errors': errors})

    async def on_connect(self) -> None:
        """Override to handle an incoming websocket connection"""
        await self.websocket.accept()

    async def on_disconnect(self, close_code: int) -> None:
        """Override to handle a disconnecting websocket"""
