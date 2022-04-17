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
    Class representation of a handler. It holds information about the handler, e.g. :attr:`model`
    (based on :class:`pydantic.BaseModel`), :attr:`event`, etc

    :param str event: name of the event this handler is for
    :param typing.Callable method: method this handler will call
    :param pydantic.BaseModel response_model:
        :meth:`handle` will parse the return value of :attr:`method` into this model. If no model
        is given a default response model will be created.
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
        #: Based on :class:`.WebSocketEventMessage` with fields for the parameters of
        #: :attr:`method`. Will be used for input validation.
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
        """
        Will be called by :meth:`.WebSocketHandlingEndpoint.on_receive`

        :param WebSocketEventMessage msg: will be validated against :attr:`model`
        :returns: :attr:`response_model`
        :rtype: WebSocketEventMessage
        """
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


@typing.overload
def on_event(event: typing.Callable) -> typing.Callable:
    """
    If the decorator is used without parentheses it's only argument will be the method itself.
    :meta private:
    """


@typing.overload
def on_event(
    event: str | None = None,
    response_model: typing.Type[BaseModel] | None = None,
) -> typing.Callable:
    pass


def on_event(
    event: str | typing.Callable | None = None,
    response_model: typing.Type[BaseModel] | None = None,
) -> typing.Callable:
    """
    Turns a :class:`typing.Callable` into a :class:`Handler`
    Decorator to be used in subclasses of :class:`.WebSocketHandlingEndpoint`
    Declares a method as handler for :attr:`event`

    Takes the same parameters as :class:`Handler`

    Technical Note: Since it's impossible to get the class of an unbound function this decorator
    just sets some attributes on the function. The registration as handler happens in
    :class:`.HandlingEndpointMeta`:meth:`.__new__`
    """

    def decorator(func: typing.Callable) -> Handler:
        # if decorator is used without parantheses the first argument will be the function itself
        event_name = None if callable(event) else event
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

    if callable(event):
        return decorator(event)
    else:
        return decorator
