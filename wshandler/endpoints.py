import typing
import json

from starlette import status
from starlette.types import Message, Receive, Scope, Send
from starlette.websockets import WebSocket, WebSocketDisconnect

class WebSocketEndpoint:
    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "websocket"
        self.scope = scope
        self.receive = receive
        self.send = send
        self.websocket = WebSocket(self.scope, receive=self.receive, send=self.send)

    def __await__(self) -> typing.Generator:
        return self.dispatch().__await__()

    async def dispatch(self) -> None:
        await self.on_connect()

        close_code = status.WS_1000_NORMAL_CLOSURE

        try:
            while True:
                try:
                    data = await self.websocket.receive_json()
                    await self.on_receive(data)
                except json.decoder.JSONDecodeError:
                    await self.websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                    raise RuntimeError("Malformed JSON data received.")
                except WebSocketDisconnect as exc:
                    close_code = exc.code

        except Exception as exc:
            close_code = status.WS_1011_INTERNAL_ERROR
            raise exc
        finally:
            await self.on_disconnect(close_code)

    async def on_connect(self) -> None:
        """Override to handle an incoming websocket connection"""
        await self.websocket.accept()

    async def on_receive(self, data: typing.Any) -> None:
        """Override to handle an incoming websocket message"""

    async def on_disconnect(self, close_code: int) -> None:
        """Override to handle a disconnecting websocket"""
