"""This module provides the :class:`WebSocketHandlingEndpoint`"""
import typing
import json
import logging
from enum import Enum

from starlette import status
from starlette.types import Receive, Scope, Send
from starlette.exceptions import HTTPException
from starlette.websockets import WebSocket, WebSocketDisconnect
from pydantic import ValidationError, create_model, Extra
from fastapi.encoders import jsonable_encoder
from fastapi.dependencies.utils import get_typed_signature, get_param_field

from .models import WebSocketEventMessage

if typing.TYPE_CHECKING:
    from pydantic.error_wrappers import ErrorDict

class Handler:
    """
    Class representation of a handler. It holds information about the handler, e.g. input model
    (based on :class:`pydantic.BaseModel`), :param:`event`, etc
    """
    def __init__(self, event: str, method: typing.Callable) -> None:
        self.event = event
        self.method = method

        self.model = create_model(f'{event}_data', __base__=WebSocketEventMessage)
        self.model.__config__.extra = Extra.forbid
        sig = get_typed_signature(method)

        for param_name, param in sig.parameters.items():
            field = get_param_field(param_name=param_name, param=param)
            self.model.__fields__[param_name] = field

    async def __call__(self, **kwargs: typing.Any) -> typing.Generator:
        return await self.method(**kwargs)

def on_event(event: str) -> typing.Callable:
    """
    Should only be used in subclasses of :class:`WebSocketHandlingEndpoint`
    Declares a method as handler for :param:`event`

    Technical Note: this decorator just sets some attributes on the function. The registration as
    handler happens in :meth:`WebSocketHandlingEndpoint.__init__`
    """
    def decorator(func: typing.Callable) -> typing.Callable:
        setattr(func, '__handler_event', event)
        return func
    return decorator

class WebSocketHandlingEndpoint:
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
    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "websocket"
        self.scope = scope
        self.receive = receive
        self.send = send
        self.websocket = WebSocket(self.scope, receive=self.receive, send=self.send)
        self.handlers: typing.Dict[str, Handler] = {}

        # register all methods starting with on_ as handlers
        for methodname in dir(self):
            handler_method = getattr(self, methodname)

            if hasattr(handler_method, '__handler_event'):
                self.set_handler(getattr(handler_method, '__handler_event'), handler_method)
            elif methodname.startswith('on_') and methodname not in \
                    ['on_connect', 'on_receive', 'on_disconnect']:
                assert callable(handler_method), 'handler methods have to be callable'
                self.set_handler(methodname[3:], handler_method)

        self.__update_event_message_model()

    def __update_event_message_model(self) -> None:
        self.event_message_model = create_model(
            'WebSocketEventMessage',
            type=(Enum('type', [(event, event) for event in self.handlers]), ...),
            __base__=WebSocketEventMessage
        )

    def __await__(self) -> typing.Generator:
        return self.dispatch().__await__()

    def set_handler(
            self,
            event: str,
            method: typing.Callable,
            ) -> None:
        """
        Register a handler for event
        """
        assert event not in ['connect', 'disconnect', 'receive'], f'{event} is reserved'

        if method is None:
            del self.handlers[event]
            logging.debug('Clearing handler for %s', event)
        elif event in self.handlers:
            logging.warning("Overwriting handler for %s with %s", event, method)
        else:
            self.handlers[event] = Handler(event, method)

        if hasattr(self, 'event_message_model'):
            self.__update_event_message_model()

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
                except json.decoder.JSONDecodeError as exc:
                    await self.websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                    raise RuntimeError("Malformed JSON data received.") from exc
                except ValidationError as exc:
                    await self.send_exception(exc)
                except WebSocketDisconnect as exc:
                    close_code = exc.code
                else:
                    try:
                        await self.handle(msg)
                    except WebSocketDisconnect as exc:
                        close_code = exc.code
                    except ValidationError as exc:
                        await self.send_exception(exc)
                    except HTTPException as exc:
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

    async def handle(self, msg: WebSocketEventMessage) -> None:
        """Calls the handler for the incoming ``msg``"""
        assert msg.type in self.handlers, 'handle called for unknown event'
        logging.debug("Calling handler for message %s", msg)

        # todo validate incoming data
        handler = self.handlers[msg.type]
        data = handler.model.parse_obj(msg).dict()
        for msgfield in WebSocketEventMessage.__fields__:
            del data[msgfield]
        response = await self.handlers[msg.type](**data)

        if response is not None:
            #TODO validate response
            self.send_json(response)

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
