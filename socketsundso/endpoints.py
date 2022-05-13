"""
The WebSocket Handling Endpoint

This is the heart of :mod:`socketsundso`. To create a WebSocket JSON API create a subclass of
:class:`WebSocketHandlingEndpoint` with some :class:`.Handler` s.

For example:

.. code-block:: python

   from socketsundso import WebSocketHandlingEndpoint, event

   class MyWSApp(WebSocketHandlingEndpoint):
     @event
     async def hello_world(self):
       return {'message': 'hello_world'}

To be used with `fastapi.routing.APIWebSocketRoute` (e.g. via `@app.websocket` or
`app.add_api_websocket_route`).
"""
import json
import typing

from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from starlette import status
from starlette.exceptions import HTTPException
from starlette.websockets import WebSocket

from .handler import Dispatcher

if typing.TYPE_CHECKING:
    from pydantic.error_wrappers import ErrorDict


class WebSocketHandlingEndpoint(Dispatcher):
    """
    The WebSocketHandlingEndpoint is a class for the creation of a simple JSON-based WebSocket API

    This class is based on :class:`starlette.endpoints.WebSocketEndpoint` but by default takes a
    :class:`fastapi.WebSocket` as argument, so it can be used with
    :meth:`fastapi.routing.add_api_websocket_route`

    Incoming messages have to be based on :class:`EventMessage`

    :meth:`dispatch` will call handlers based on the incoming :attr:`EventMessage.type`.
    If the handler returns something it will be send to the client.

    To register a method as handler decorate it with :meth:`socketsundso.handler.event` or
    :meth:`event`.


    You can override :meth:`on_connect` and :meth:`on_disconnect` to change what happens when
    clients connect or disconnect.

    If you want to inject `dependencies`_ you will have to extend :meth:`__init__`.

    .. _dependencies: https://fastapi.tiangolo.com/tutorial/dependencies/
    """

    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket
        super().__init__()

    def __await__(self) -> typing.Generator:
        return self.dispatch().__await__()

    async def dispatch(self) -> None:
        """
        Handles the lifecycle of a :class:`WebSocket` connection and calls :meth:`on_connect` and
        :meth:`on_disconnect` repectively.
        If a message is received the corresponding :meth:`Handler.handle_event` will be called and
        the response is passed to :meth:`respond`

        .. note:: This method will be called by :mod:`starlette`. You shouldn't need to think about
                  it.

        If the client sends a JSON payload that can't be validated by :class:`EventMessage`
        or :meth:`.Handler.handle_event` raises an :exc:`ValidationError` or
        :exc:`json.decoder.JSONDecodeError` the errors will be send to the client via
        :meth:`send_exception`.
        """
        await self.on_connect()

        close_code = status.WS_1000_NORMAL_CLOSURE

        try:
            while True:
                message = await self.websocket.receive()
                if message["type"] == "websocket.receive":
                    try:
                        response = await self.handle(**json.loads(message["text"]))

                        if response is not None:
                            await self.respond(response)
                    except ValidationError as exc:
                        await self.send_exception(exc)
                    except json.decoder.JSONDecodeError:
                        await self.websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                        raise RuntimeError("Malformed JSON data received.")

                elif message["type"] == "websocket.disconnect":
                    close_code = int(message.get("code", status.WS_1000_NORMAL_CLOSURE))
                    break
        except Exception as exc:
            close_code = status.WS_1011_INTERNAL_ERROR
            raise exc
        finally:
            await self.on_disconnect(close_code)

    async def send_exception(self, exc: Exception) -> None:
        """
        Formats the ``exc`` and sends it to the client (via :meth:`respond`)

        Override if you don't wnat to send any Exceptions to the client or want to format them
        differently.
        """
        errors: typing.List[typing.Dict[str, typing.Any]] | typing.List[ErrorDict]

        if isinstance(exc, ValidationError):
            errors = exc.errors()
        elif isinstance(exc, HTTPException):
            errors = [
                {
                    "msg": exc.detail,
                    "status_code": exc.status_code,
                    "type": type(exc).__name__,
                }
            ]
        else:
            errors = [{"msg": str(exc), "type": type(exc).__name__}]

        await self.respond({"errors": errors})

    async def respond(self, response: typing.Any) -> None:
        """
        Calls :meth:`fastapi.encoders.jsonable_encoder` and passes result to
        :meth:`starlette.websockets.WebSocket.send_json`.

        Override to handle outgoing messages differently.
        For example you could handle handler response differently based on their type.
        """
        return await self.websocket.send_json(jsonable_encoder(response))

    async def on_connect(self) -> None:
        """
        Override to handle an incoming websocket connection

        .. note:: Don't forget to call :meth:`self.websocket.accept` to accept the connection.
        """
        await self.websocket.accept()

    async def on_disconnect(self, close_code: int) -> None:
        """Override to handle a disconnecting websocket"""
