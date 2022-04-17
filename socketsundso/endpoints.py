"""The WebSocket Endpoint"""
import json
import typing
from types import MethodType

from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError, create_model
from starlette import status
from starlette.exceptions import HTTPException
from starlette.types import Receive, Scope, Send
from starlette.websockets import WebSocket

from .handler import Handler, on_event
from .models import WebSocketEventMessage

if typing.TYPE_CHECKING:
    from pydantic.error_wrappers import ErrorDict


class HandlingEndpointMeta(type):
    """
    Metaclass for :class:`WebSocketHandlingEndpoint`

    All this does is put every :class:`.Handler` inside of :class:`WebSocketHandlingEndpoint` into
    :attr:`WebSocketHandlingEndpoint.handlers`
    """

    def __new__(cls: typing.Type[type], *args: str, **kwargs: typing.Any) -> type:
        endpoint = type.__new__(cls, *args, **kwargs)

        handlers = {}

        # find all handlers and add them to handlers
        for methodname in dir(endpoint):
            method = getattr(endpoint, methodname)

            if isinstance(method, Handler):
                assert (
                    method.event not in handlers
                ), f"duplicate handler for {method.event}"
                handlers[method.event] = method

        setattr(endpoint, "handlers", handlers)
        return endpoint


class WebSocketHandlingEndpoint(metaclass=HandlingEndpointMeta):
    """
    The WebSocketHandlingEndpoint is a class for the creation of a simple JSON-based WebSocket API

    This class is based on :class:`starlette.endpoints.WebSocketEndpoint`
    Incoming messages have to be based on :class:`WebSocketEventMessage`

    :meth:`dispatch` will call handlers based on the incoming :attr:`WebSocketEventMessage.type`.
    If the handler returns something it will be send to the client.

    To register a method as handler decorate it with :meth:`socketsundso.handler.on_event` or
    :meth:`on_event`.


    You can override :meth:`on_connect` and :meth:`on_disconnect` to change what happens when
    clients connect or disconnect.
    """

    handlers: typing.Dict[str, Handler] = {}

    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "websocket"
        self.scope = scope
        self.receive = receive
        self.send = send
        #: :class:`WebSocket` instance
        self.websocket = WebSocket(self.scope, receive=self.receive, send=self.send)

        # add all available events to our model
        self.event_message_model = create_model(
            "WebSocketEventMessage",
            type=(typing.Literal[tuple(self.handlers.keys())], ...),
            __base__=WebSocketEventMessage,
        )

        # we need to tell give the handlers some bound methods
        for handler in self.handlers.values():
            # check if handler.method is on of our methods
            if handler in self.__class__.__dict__.values() and not isinstance(
                handler.method, (classmethod, staticmethod)
            ):
                handler.bound_method = MethodType(handler.method, self)

    def __await__(self) -> typing.Generator:
        return self.dispatch().__await__()

    @classmethod
    def on_event(cls, *args: typing.Any, **kwargs: typing.Any) -> typing.Callable:
        """
        .. seealso:: Same arguments as :meth:`socketsundso.handler.on_event`.
        """

        def decorator(func: typing.Callable) -> Handler:
            # just call the on_event decorator defined in handler.py
            handler: Handler = on_event(*args, **kwargs)(func)
            assert (
                handler.event not in cls.handlers
            ), f"duplicate handler for {handler.event}"
            cls.handlers[handler.event] = handler
            return handler

        return decorator

    async def dispatch(self) -> None:
        """
        Handles the lifecycle of a :class:`WebSocket` connection and calls :meth:`on_connect`,
        the :meth:`on_receive` and :meth:`on_disconnect` repectively.

        .. note:: This method will be called by :mod:`starlette`. You shouldn't need to think about
                  it.

        If the client sends a JSON payload that can't be validated by :class:`WebSocketEventMessage`
        or :meth:`on_receive` raises an :exc:`ValidationError` or
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
                        data = self.event_message_model(**json.loads(message["text"]))
                        await self.on_receive(data)
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

    async def on_receive(self, message: WebSocketEventMessage) -> None:
        """
        Called by :meth:`dispatch` whenever a message arrives.

        Calls the :meth:`Handler.handle()` for the event and calls :meth:`send_json` with the
        response.
        """
        assert message.type in self.handlers, "on_receive called with unknown event"
        response = await self.handlers[message.type].handle(message)

        if response is not None:
            await self.send_json(response)

    async def send_exception(self, exc: Exception) -> None:
        """
        Formats the ``exc`` and sends it to the client (via :meth:`send_json`)

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

        await self.send_json({"errors": errors})

    async def send_json(self, response: typing.Any) -> None:
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
