""":class:`Handler` and related methods"""
import typing

from pydantic import create_model, Extra, BaseConfig
from fastapi.dependencies.utils import get_typed_signature, get_param_field

from .models import WebSocketEventMessage

class Handler:
    """
    Class representation of a handler. It holds information about the handler, e.g. input model
    (based on :class:`pydantic.BaseModel`), :param:`event`, etc
    """
    def __init__(self, event: str, method: typing.Callable) -> None:
        self.event = event
        self.method = method

        class Config(BaseConfig):
            extra = Extra.forbid

        self.model = create_model(f'WebSocketEventMessage_{event}',
                type=(typing.Literal[event],...), __config__=Config)
        self.model.__config__.extra = Extra.forbid
        sig = get_typed_signature(method)

        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            field = get_param_field(param_name=param_name, param=param)
            self.model.__fields__[param_name] = field

    async def __call__(self, msg: WebSocketEventMessage) -> typing.Generator:
        data = self.model.parse_obj(msg).dict(exclude={'type'})
        return await self.method(**data)


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
