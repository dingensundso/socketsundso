""":class:`Handler` and related methods"""
import typing

from pydantic import create_model, Extra
from fastapi.dependencies.utils import get_typed_signature, get_param_field

class Handler:
    """
    Class representation of a handler. It holds information about the handler, e.g. input model
    (based on :class:`pydantic.BaseModel`), :param:`event`, etc
    """
    def __init__(self, event: str, method: typing.Callable) -> None:
        self.event = event
        self.method = method

        class Config:
            extra = Extra.forbid

        self.model = create_model(f'WebSocketEventMessage_{event}', type=(typing.Literal[event],...), __config__=Config)
        self.model.__config__.extra = Extra.forbid
        sig = get_typed_signature(method)

        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            field = get_param_field(param_name=param_name, param=param)
            self.model.__fields__[param_name] = field

    async def __call__(self, *args, **kwargs: typing.Any) -> typing.Generator:
        return await self.method(*args, **kwargs)

class HandlingEndpointMeta(type):
    def __new__(metacls, name, bases, namespace, **kwargs):
        cls = super().__new__(metacls, name, bases, namespace, **kwargs)
        setattr(cls, 'handlers', {})

        for methodname in dir(cls):
            handler_method = getattr(cls, methodname)

            if hasattr(handler_method, '__handler_event'):
                cls.set_handler(getattr(handler_method, '__handler_event'), handler_method)
            elif methodname.startswith('on_') and methodname not in \
                    ['on_connect', 'on_receive', 'on_disconnect']:
                assert callable(handler_method), 'handler methods have to be callable'
                cls.set_handler(methodname[3:], handler_method)

        return cls


def on_event(event: str) -> typing.Callable:
    """
    Should only be used in subclasses of :class:`WebSocketHandlingEndpoint`
    Declares a method as handler for :param:`event`

    Technical Note: Since it's impossible to get the class of an unbound function this decorator
    just sets some attributes on the function. The registration as handler happens in
    :meth:`HandlingEndpointMeta.__new__`
    """
    def decorator(func: typing.Callable) -> typing.Callable:
        setattr(func, '__handler_event', event)
        return func
    return decorator
