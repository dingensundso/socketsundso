"""This module provides the :class:`WebSocketHandlingEndpoint`"""
import typing
import json
import logging
from types import MethodType

from starlette import status
from starlette.types import Receive, Scope, Send
from starlette.exceptions import HTTPException
from starlette.websockets import WebSocket, WebSocketDisconnect
from pydantic import ValidationError, create_model, BaseModel
from fastapi.encoders import jsonable_encoder

from .models import WebSocketEventMessage
from .handler import Handler

if typing.TYPE_CHECKING:
    from pydantic.error_wrappers import ErrorDict

class HandlingEndpointMeta(type):
    def __new__(cls: typing.Type[type], *args: str, **kwargs: typing.Any) -> type:
        endpoint = type.__new__(cls, *args, **kwargs)

        handlers = {}

        for methodname in dir(endpoint):
            method = getattr(endpoint, methodname)

            # convert on_... methods to Handlers
            if methodname.startswith('on_') and methodname not in \
                    ['on_connect', 'on_receive', 'on_disconnect', 'on_event']:
                assert callable(method), 'handler methods have to be callable'
                method = Handler(methodname[3:], method)
                setattr(endpoint, methodname, method)

            if isinstance(method, Handler):
                assert method.event not in handlers
                handlers[method.event] = method

        setattr(endpoint, 'handlers', handlers)
        return endpoint

class WebSocketHandlingEndpoint(metaclass=HandlingEndpointMeta):
    """
    The WebSocketHandlingEndpoint is a class for the creation of a simple JSON-based WebSocket API

    This class is based on :class:`starlette.endpoints.WebSocketEndpoint`
    Incoming messages have to be based on :class:`WebSocketEventMessage`

    :meth:`dispatch` will call handlers based on the incoming :attr:`WebSocketEventMessage.type`.
    If the handler returns something it will be send to the client.

    To register a handler name it on_[type] or decorate it with :meth:`handler` and the
    :meth:`__init__` function will take care of it.


    You can override :meth:`on_connect` and :meth:`on_disconnect` to change what happens when
    clients connect or disconnect.
    """
    handlers: typing.Dict[str, Handler] = {}

    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "websocket"
        self.scope = scope
        self.receive = receive
        self.send = send
        self.websocket = WebSocket(self.scope, receive=self.receive, send=self.send)

        # add all available events to our model
        self.event_message_model = create_model(
            'WebSocketEventMessage',
            type=(typing.Literal[tuple(self.handlers.keys())], ...),
            __base__=WebSocketEventMessage
        )

        # we need to tell give the handlers some bound methods
        for handler in self.handlers.values():
            # check if handler.method is on of our methods
            if handler in self.__class__.__dict__.values() \
                   and not isinstance(handler.method, (classmethod, staticmethod)):
                handler.bound_method = MethodType(handler.method, self)

    def __await__(self) -> typing.Generator:
        return self.dispatch().__await__()

    @classmethod
    def on_event(
        cls,
        event: str,
        response_model: typing.Type[BaseModel] | None = None
    ) -> typing.Callable:
        """
        Declares a method as handler for :param:`event`
        """
        def decorator(func: typing.Callable) -> Handler:
            assert event not in cls.handlers
            handler = Handler(event, func, response_model = response_model)
            cls.handlers[event] = handler
            return handler
        return decorator

    async def dispatch(self) -> None:
        """
        Handles the lifecycle of a :class:`WebSocket` connection and calls :meth:`on_connect`,
        the :meth:`handle` and :meth:`on_disconnect` repectively.

        This method will be called by starlette.

        If the client sends a JSON payload that does not conform to :class:`WebSocketEventMessage`
        or :meth:`handle` raises an :exc:`Exception` the errors will be send to the client via
        :meth:`send_exception`.
        """
        await self.on_connect()

        close_code = status.WS_1000_NORMAL_CLOSURE

        try:
            while True:
                try:
                    data = await self.websocket.receive_json()
                    msg = self.event_message_model(**data)
                    await self.handle(msg)
                except json.decoder.JSONDecodeError as exc:
                    await self.websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                    raise RuntimeError("Malformed JSON data received.") from exc
                except ValidationError as exc:
                    await self.send_exception(exc)
                except WebSocketDisconnect as exc:
                    close_code = exc.code
                except Exception as exc:
                    raise exc

        except Exception as exc:
            close_code = status.WS_1011_INTERNAL_ERROR
            raise exc
        finally:
            await self.on_disconnect(close_code)

    async def handle(self, msg: WebSocketEventMessage) -> None:
        """Calls the handler for the incoming ``msg``"""
        assert msg.type in self.handlers, 'handle called for unknown event'
        logging.debug("Calling handler for message %s", msg)

        response = await self.handlers[msg.type].handle(msg)

        if response is not None:
            await self.send_json(response)

    async def send_exception(self, exc: Exception) -> None:
        """
        Formats the ``exc`` and sends it to the client (via :meth:`send_json`)

        Override if you don't wnat to send any Exceptions to the client or want to format them
        differently.
        """
        errors: typing.List[typing.Dict[str,typing.Any]] | typing.List[ErrorDict] # pylint: disable=used-before-assignment

        if isinstance(exc, ValidationError):
            errors = exc.errors()
        elif isinstance(exc, HTTPException):
            errors = [{
                'msg': exc.detail,
                'status_code': exc.status_code,
                'type': type(exc).__name__}]
        else:
            errors = [{'msg': str(exc), 'type': type(exc).__name__}]

        await self.send_json({'errors': errors})

    async def send_json(self, response: typing.Any) -> None:
        """
        Override to handle outgoing messages

        For example you could handle handler response differently based on their type.
        """
        return await self.websocket.send_json(jsonable_encoder(response))

    async def on_connect(self) -> None:
        """Override to handle an incoming websocket connection"""
        await self.websocket.accept()

    async def on_disconnect(self, close_code: int) -> None:
        """Override to handle a disconnecting websocket"""
