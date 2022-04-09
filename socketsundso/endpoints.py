"""This module provides the :class:`WebSocketHandlingEndpoint`"""
import typing
import json
import logging
import inspect
from functools import partial

from starlette import status
from starlette.types import Receive, Scope, Send
from starlette.exceptions import HTTPException
from starlette.websockets import WebSocket, WebSocketDisconnect
from pydantic import ValidationError, create_model
from fastapi.encoders import jsonable_encoder

from .models import WebSocketEventMessage
from .handler import Handler

if typing.TYPE_CHECKING:
    from pydantic.error_wrappers import ErrorDict

class HandlingEndpointMeta(type):
    def __new__(cls: typing.Type[type], *args: str, **kwargs: typing.Any) -> type:
        endpoint = type.__new__(cls, *args, **kwargs)
        setattr(endpoint, 'handlers', {})

        for methodname in dir(endpoint):
            method = getattr(endpoint, methodname)
            set_handler = getattr(endpoint, 'set_handler')

            if hasattr(method, '__handler_event'):
                set_handler(getattr(method, '__handler_event'), method)
            elif methodname.startswith('on_') and methodname not in \
                    ['on_connect', 'on_receive', 'on_disconnect', 'on_event']:
                assert callable(method), 'handler methods have to be callable'
                set_handler(methodname[3:], method)

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

        self.event_message_model = create_model(
            'WebSocketEventMessage',
            type=(typing.Literal[tuple(self.handlers.keys())], ...),
            __base__=WebSocketEventMessage
        )

        # we need to tell the handlers that need us who we are
        for handler in self.handlers.values():
            # check if handler.method is on of our methods
            if self.__class__.__dict__.get(handler.method.__name__) == handler.method:
                handler.bind_to = self

    def __await__(self) -> typing.Generator:
        return self.dispatch().__await__()

    @classmethod
    def set_handler(
            cls,
            event: str,
            method: typing.Callable,
            ) -> None:
        """
        Declares a method as handler for :param:`event`
        """
        assert event not in ['connect', 'disconnect', 'receive'], f'{event} is reserved'

        if method is None:
            del cls.handlers[event]
            logging.debug('Clearing handler for %s', event)
        elif event in cls.handlers:
            logging.warning("Overwriting handler for %s with %s", event, method)
        else:
            cls.handlers[event] = Handler(event, method)

    @classmethod
    def on_event(cls, event: str) -> typing.Callable:
        """
        Declares a method as handler for :param:`event`
        """
        def decorator(func: typing.Callable) -> typing.Callable:
            cls.set_handler(event, func)
            return func
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
                #TODO remove this! don't send all exceptions to clients
                except Exception as exc:
                    await self.send_exception(exc)
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

        # todo validate incoming data
        response = await self.handlers[msg.type](msg)

        if response is not None:
            #TODO validate response
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
        #elif isinstance(exc, WebSocketException):
            #TODO
        else:
            errors = [{'msg': str(exc), 'type': type(exc).__name__}]

        await self.send_json({'errors': errors})

    async def send_json(self, response: typing.Any) -> None:
        """Override to handle outgoing messages"""
        return await self.websocket.send_json(jsonable_encoder(response))

    async def on_connect(self) -> None:
        """Override to handle an incoming websocket connection"""
        await self.websocket.accept()

    async def on_disconnect(self, close_code: int) -> None:
        """Override to handle a disconnecting websocket"""
