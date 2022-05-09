"""
The :class:`Handler` is a wrapper around a function.

When our app receives an :class:`.EventMessage` it will call the corresponding
:meth:`Handler.handle` for the received :attr:`type`.
The incoming :class:`.EventMessage` will be validated against :attr:`Handler.model` and the return
value of :attr:`Handler.method` will be returned as :attr:`Handler.response_model`.
"""
import typing
from inspect import unwrap
from types import MethodType

from fastapi.dependencies.utils import (
    get_param_field,
    get_typed_signature,
    is_coroutine_callable,
)
from fastapi.routing import _prepare_response_content
from fastapi.utils import create_response_field
from pydantic import BaseConfig, BaseModel, Extra, create_model
from pydantic.error_wrappers import ErrorWrapper, ValidationError
from pydantic.fields import ModelField
from starlette.concurrency import run_in_threadpool

from .models import EventMessage


class Handler:
    """
    Class representation of a handler. It holds information about the handler, e.g. :attr:`model`
    (based on :class:`pydantic.BaseModel`), :attr:`event`, etc



    :param str event:
        name of the event this handler is for
        If no event name is given the methodname will be used but leading `on_` or `handle_` will
        be stripped.
    :param typing.Callable method: method this handler will call
    :param pydantic.BaseModel response_model:
        :meth:`handle` will parse the return value of :attr:`method` into this model. If no model
        is given a default response model will be created.
    """

    def __init__(
        self,
        event: str | None = None,
        method: typing.Callable | None = None,
        response_model: typing.Type[BaseModel] | None = None,
    ) -> None:
        assert callable(method), "method has to be callable"
        assert not isinstance(method, Handler), "can't wrap Handler in Handler"

        #: The function that will be called when this :class:`Handler` is invoked
        self.method = method
        self.is_coroutine = is_coroutine_callable(unwrap(method))
        #: The event this :class:`Handler` should handle
        self.event = event or self.__get_event_name()

        # create EventMessage model for input validation
        #: Based on :class:`.EventMessage` with fields for the parameters of
        #: :attr:`method`. Will be used for input validation.
        self.model = create_model(
            f"EventMessage_{self.event}",
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

        self.__default_response = response_model is None
        # create response_model if we didn't get one
        #: Either the supplied response_model or a default one based on :class:`.EventMessage`.
        #: But it will always contain :attr:`type`
        self.response_model = response_model or create_model(
            f"Response_{self.event}",
            type=self.event,
            __config__=type("Config", (BaseConfig,), {"extra": Extra.allow}),
        )

        self.__type_field = ModelField(
            name="type",
            type_=str,
            class_validators=None,
            default=self.event,
            required=False,
            model_config=BaseConfig,
        )

        # ensure type is in there
        if "type" not in self.response_model.__fields__:
            self.response_model.__fields__["type"] = self.__type_field

        self.response_field = create_response_field(
            name=f"Response_{self.event}", type_=self.response_model, required=True
        )

    async def __call__(
        self,
        *args: typing.Any,
        event_message: EventMessage | None = None,
        **kwargs: typing.Any,
    ) -> typing.Any:
        """
        If the only keyword-argument is event_message call :meth:`handle_event`.

        Otherwise just call :attr:`method`
        """
        if (
            event_message is not None
            and len(kwargs) == 0
            and isinstance(event_message, EventMessage)
        ):
            return await self.handle_event(
                event_message,
                method=self.method.__get__(*args) if len(args) == 1 else None,
            )
        if self.is_coroutine:
            return await self.method(*args, **kwargs)
        else:
            return await run_in_threadpool(self.method, *args, **kwargs)

    def __get__(
        self, obj: typing.Any, type: typing.Type | None = None
    ) -> typing.Union["Handler", MethodType]:
        if obj is not None:
            MethodType(self, obj)
        return self

    def __get_event_name(self) -> str:
        if self.method.__name__.startswith("on_"):
            event_name = self.method.__name__[3:]
        elif self.method.__name__.startswith("handle_"):
            event_name = self.method.__name__[7:]
        else:
            event_name = self.method.__name__
        assert len(event_name) > 0, "event name has to be at leas 1 character"
        return event_name

    async def handle_event(
        self, event_message: EventMessage, *, method: typing.Callable | None = None
    ) -> BaseModel | None:
        """
        Handle incoming :class:`.EventMessage`

        If `method` is given use that instead of :attr:`method`

        :param EventMessage msg: will be validated against :attr:`model`
        :returns: :attr:`response_model`
        :rtype: :class:`.EventMessage`
        :raises: :class:`ValidationError`
        """
        errors = []
        field = self.response_field
        data = self.model.parse_obj(event_message).dict(exclude={"type"})
        method = method or self.method
        response_data = (
            await method(**data)
            if self.is_coroutine
            else await run_in_threadpool(method, **data)
        )
        response_content = _prepare_response_content(
            response_data,
            exclude_unset=False,
            exclude_defaults=False,
            exclude_none=False,
        )

        if response_content is None:
            return None

        # if we didn't get a response_model but got a model now, use it!
        if self.__default_response and isinstance(response_data, BaseModel):
            # make sure type is in there
            if "type" not in response_data.__fields__:
                response_data.__fields__["type"] = self.__type_field

            field = create_response_field(
                name=f"Response_{self.event}", type_=type(response_data), required=True
            )

        value, errors_ = field.validate(response_content, {}, loc=("response",))
        if isinstance(errors_, ErrorWrapper):
            errors.append(errors_)
        elif isinstance(errors_, list):
            errors.extend(errors_)
        if errors:
            raise ValidationError(errors, field.type_)
        return value


@typing.overload
def event(event: typing.Callable) -> typing.Callable:
    """
    If the decorator is used without parentheses it's only argument will be the method itself.
    :meta private:
    """


@typing.overload
def event(
    event: str | None = None,
    response_model: typing.Type[BaseModel] | None = None,
) -> typing.Callable:
    pass


def event(
    event: str | typing.Callable | None = None,
    response_model: typing.Type[BaseModel] | None = None,
) -> typing.Callable:
    """
    Decorator to easily create a :class:`Handler`.

    .. note::
      To attach the :class:`Handler` to a :class:`.WebSocketHandlingEndpoint` use
      :meth:`.WebSocketHandlingEndpoint.attach_handler`.

      Alternativly you could just use :meth:`.WebSocketHandlingEndpoint.event` to do both steps.
    """

    def decorator(func: typing.Callable) -> Handler:
        return Handler(
            event if not callable(event) else None,
            func,
            response_model=response_model,
        )

    if callable(event):
        return decorator(event)
    else:
        return decorator
