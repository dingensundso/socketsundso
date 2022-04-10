""":class:`Handler` and related methods"""
import typing

from pydantic import create_model, Extra, BaseConfig, BaseModel
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
        self.model = self.__create_model()
        self.bound_method = None

    async def __call__(self, *args, **kwargs) -> typing.Generator:
        method = self.method if self.bound_method is None else self.bound_method
        return await method(*args, **kwargs)

    async def handle(self, msg: WebSocketEventMessage) -> typing.Generator:
        data = self.model.parse_obj(msg).dict(exclude={'type'})
        return await self(**data)

    def __create_model(self) -> BaseModel:
        class Config(BaseConfig):
            extra = Extra.forbid

        model = create_model(f'WebSocketEventMessage_{self.event}',
                type=(typing.Literal[self.event],...), __config__=Config)

        sig = get_typed_signature(self.method)
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            field = get_param_field(param_name=param_name, param=param)
            model.__fields__[param_name] = field
        return model


def on_event(event: str) -> typing.Callable:
    """
    Should only be used in subclasses of :class:`WebSocketHandlingEndpoint`
    Declares a method as handler for :param:`event`

    Technical Note: Since it's impossible to get the class of an unbound function this decorator
    just sets some attributes on the function. The registration as handler happens in
    :meth:`HandlingEndpointMeta.__new__`
    """
    def decorator(func: typing.Callable) -> Handler:
        return Handler(event, func)
    return decorator
