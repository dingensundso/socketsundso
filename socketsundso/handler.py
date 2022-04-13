""":class:`Handler` and related methods"""
import typing

from pydantic import create_model, Extra, BaseConfig, BaseModel, Field
from pydantic.fields import FieldInfo
from pydantic.error_wrappers import ErrorWrapper, ValidationError
from fastapi.dependencies.utils import get_typed_signature, get_param_field
from fastapi.routing import _prepare_response_content
from fastapi.utils import create_response_field

from .models import WebSocketEventMessage

class Handler:
    """
    Class representation of a handler. It holds information about the handler, e.g. input model
    (based on :class:`pydantic.BaseModel`), :param:`event`, etc
    """
    def __init__(
        self,
        event: str,
        method: typing.Callable,
        response_model: typing.Type[BaseModel] | None = None
    ) -> None:
        self.event = event
        self.method = method

        self.bound_method: typing.Callable | None = None

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
        if response_model is None:
            self.response_model = create_model(
                f"Response_{event}",
                type=event,
                __config__=type("Config", (BaseConfig,), {'extra': Extra.allow})
            )
        else:
            self.response_model = response_model

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

    async def __call__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Generator:
        method = self.method if self.bound_method is None else self.bound_method
        return await method(*args, **kwargs)

    async def handle(self, msg: WebSocketEventMessage) -> BaseModel | None:
        errors = []
        field = self.response_field
        data = self.model.parse_obj(msg).dict(exclude={'type'})
        response_content = _prepare_response_content(
            await self(**data),
            exclude_unset=False,
            exclude_defaults=False,
            exclude_none=False
        )

        if response_content is None:
            return None

        value, errors_ = field.validate(response_content, {}, loc=("response",))
        if isinstance(errors_, ErrorWrapper):
            errors.append(errors_)
        elif isinstance(errors_, list):
            errors.extend(errors_)
        if errors:
            raise ValidationError(errors, field.type_)
        return value

def on_event(event: str, response_model: typing.Type[BaseModel] | None = None) -> typing.Callable:
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
