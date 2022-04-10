""":class:`Handler` and related methods"""
import typing

from pydantic import create_model, Extra, BaseConfig, BaseModel
from pydantic.fields import ModelField
from fastapi.dependencies.utils import get_typed_signature, get_param_field
from fastapi.routing import serialize_response, create_response_field
from fastapi.encoders import jsonable_encoder

from .models import WebSocketEventMessage

class Handler:
    """
    Class representation of a handler. It holds information about the handler, e.g. input model
    (based on :class:`pydantic.BaseModel`), :param:`event`, etc
    """
    def __init__(self, event: str, method: typing.Callable, response_model: typing.Optional[ModelField] = None) -> None:
        self.event = event
        self.method = method
        self.response_model = response_model
        if self.response_model:
            self.response_field = create_response_field(
                name=f"Response_{self.event}", type_=self.response_model
            )
        else:
            self.response_field = None

        self.model = self.__create_model()
        self.bound_method = None

    async def __call__(self, *args, **kwargs) -> typing.Generator:
        method = self.method if self.bound_method is None else self.bound_method
        return await method(*args, **kwargs)

    async def handle(self, msg: WebSocketEventMessage) -> typing.Generator:
        data = self.model.parse_obj(msg).dict(exclude={'type'})
        response_content = await self(**data)
        return await serialize_response(field = self.response_field, response_content = response_content)

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


def on_event(event: str, response_model = None) -> typing.Callable:
    """
    Should only be used in subclasses of :class:`WebSocketHandlingEndpoint`
    Declares a method as handler for :param:`event`

    Technical Note: Since it's impossible to get the class of an unbound function this decorator
    just sets some attributes on the function. The registration as handler happens in
    :meth:`HandlingEndpointMeta.__new__`
    """
    def decorator(func: typing.Callable) -> Handler:
        return Handler(event, func, response_model = response_model)
    return decorator
