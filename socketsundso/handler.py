""":class:`Handler` and related methods"""
import typing

from pydantic import create_model, Extra, BaseConfig, BaseModel, Field
from pydantic.fields import ModelField, FieldInfo
from fastapi.dependencies.utils import get_typed_signature, get_param_field
from fastapi.routing import serialize_response
from fastapi.encoders import jsonable_encoder
from fastapi.utils import create_cloned_field, create_response_field

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

        self.bound_method = None

        # create EventMessage model for input validation
        self.model = create_model(f'WebSocketEventMessage_{self.event}',
            type=(typing.Literal[self.event],...),
            __config__=type("Config", (BaseConfig,), {'extra': Extra.forbid})
        )

        # add all arguments (except for self) to the model
        signature = get_typed_signature(self.method)
        for param_name, param in signature.parameters.items():
            if param_name == 'self':
                continue
            field = get_param_field(param_name=param_name, param=param)
            self.model.__fields__[param_name] = field

        # create response_model if we didn't get one
        if self.response_model is None:
            self.response_model = create_model(
                f"Response_{event}",
                type=event,
                __config__=type("Config", (BaseConfig,), {'extra': Extra.allow})
            )

        # ensure type is in there
        if 'type' not in self.response_model.__fields__:
            self.response_model.__fields__['type'] = Field(name='type',
                    type_=str,
                    required=False,
                    default=event,
                    field_info = FieldInfo(None)
            )

        self.response_field = create_response_field(
            name=f"Response_{self.event}",
            type_=self.response_model,
            required=True
        )

    async def __call__(self, *args, **kwargs) -> typing.Generator:
        method = self.method if self.bound_method is None else self.bound_method
        return await method(*args, **kwargs)

    async def handle(self, msg: WebSocketEventMessage) -> typing.Generator:
        data = self.model.parse_obj(msg).dict(exclude={'type'})
        response_content = await self(**data)
        return await serialize_response(field = self.response_field, response_content = response_content)


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
