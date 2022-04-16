""":class:`Handler` and related methods"""
import typing

from fastapi.dependencies.utils import get_param_field, get_typed_signature
from fastapi.routing import _prepare_response_content
from fastapi.utils import create_response_field
from pydantic import BaseConfig, BaseModel, Extra, Field, create_model
from pydantic.error_wrappers import ErrorWrapper, ValidationError
from pydantic.fields import FieldInfo

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
        response_model: typing.Type[BaseModel] | None = None,
    ) -> None:
        self.event = event
        self.method = method

        self.bound_method: typing.Callable | None = None

        # create EventMessage model for input validation
        self.model = create_model(
            f"WebSocketEventMessage_{self.event}",
            type=(typing.Literal[self.event], ...),
            __config__=type("Config", (BaseConfig,), {"extra": Extra.forbid}),
        )

        # add all arguments (except for self) to the model
        signature = get_typed_signature(self.method)
        for param_name, param in signature.parameters.items():
            if param_name == "self":
                continue
            field = get_param_field(param_name=param_name, param=param)
            self.model.__fields__[param_name] = field

        # create response_model if we didn't get one
        if response_model is None:
            self.response_model = create_model(
                f"Response_{event}",
                type=event,
                __config__=type("Config", (BaseConfig,), {"extra": Extra.allow}),
            )
        else:
            self.response_model = response_model

        # ensure type is in there
        if "type" not in self.response_model.__fields__:
            self.response_model.__fields__["type"] = Field(
                name="type",
                type_=str,
                required=False,
                default=event,
                field_info=FieldInfo(None),
            )

        self.response_field = create_response_field(
            name=f"Response_{self.event}", type_=self.response_model, required=True
        )

    async def __call__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        method = self.method if self.bound_method is None else self.bound_method
        return await method(*args, **kwargs)

    async def handle(self, msg: WebSocketEventMessage) -> BaseModel | None:
        errors = []
        field = self.response_field
        data = self.model.parse_obj(msg).dict(exclude={"type"})
        response_content = _prepare_response_content(
            await self(**data),
            exclude_unset=False,
            exclude_defaults=False,
            exclude_none=False,
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


def on_event(
    event_or_func: str | typing.Callable | None = None,
    response_model: typing.Type[BaseModel] | None = None,
) -> typing.Callable:
    """
    Should only be used in subclasses of :class:`WebSocketHandlingEndpoint`
    Declares a method as handler for :param:`event`
    If event is not given, the name of the function is taken as event name (but on_ or handle_ at
    the beginning will be stripped).

    Technical Note: Since it's impossible to get the class of an unbound function this decorator
    just sets some attributes on the function. The registration as handler happens in
    :meth:`HandlingEndpointMeta.__new__`
    """

    def decorator(func: typing.Callable) -> Handler:
        # if decorator is used without parantheses the first argument will be the function itself
        #        event_name = event_or_func if isinstance(event_or_func, str) else None
        event_name = None if callable(event_or_func) else event_or_func
        if event_name is None:
            if func.__name__.startswith("on_"):
                event_name = func.__name__[3:]
            elif func.__name__.startswith("handle_"):
                event_name = func.__name__[7:]
            else:
                event_name = func.__name__
            assert (
                event_name is not None
            ), "no event given and function doesn't start with on_ or handle_"
        assert len(event_name) > 0, "event name has to be at leas 1 character"

        return Handler(event_name, func, response_model=response_model)

    if callable(event_or_func):
        return decorator
    else:
        return decorator
