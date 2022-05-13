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
from pydantic.errors import WrongConstantError
from pydantic.fields import ModelField
from starlette.concurrency import run_in_threadpool

from . import decorator
from .models import EventMessage

if typing.TYPE_CHECKING:
    from pydantic.class_validators import ValidatorCallable
else:
    ValidatorCallable = typing.Any


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

    @typing.overload
    async def __call__(self, event_message: EventMessage) -> EventMessage:
        pass

    @typing.overload
    async def __call__(
        self,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> typing.Any:
        pass

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


class Dispatcher:
    """
    Baseclass of :class:`WebSocketHandlingEndpoint`

    When creating a subclass all :class:`Handler` objects will be collected so they can be easily
    called via :meth:'handle'.
    """

    handlers: typing.Dict[str, Handler] = {}

    def __init_subclass__(
        cls: typing.Type["Dispatcher"],
        /,
        overwrite_existing: bool = True,
        **kwargs: typing.Any,
    ) -> None:
        super().__init_subclass__(**kwargs)

        handlers = getattr(cls, "handlers", {}).copy()
        new_handlers: typing.Dict[str, Handler] = {}

        # find all handlers and add them to handlers
        for methodname, method in cls.__dict__.items():
            if isinstance(method, Handler):
                if not overwrite_existing:
                    assert (
                        method.event not in handlers
                    ), f"can't overwrite handler for {method.event} without overtwrite_existing"
                assert (
                    method.event not in new_handlers
                ), f"duplicate handler for {method.event}"
                new_handlers[method.event] = method

        handlers.update(new_handlers)
        cls.handlers = handlers

    def __init__(self) -> None:
        # add all available events to our model
        self.event_message_model = create_model(
            "EventMessage",
            __base__=EventMessage,
        )
        # set custom validator so changes to self.handlers are possible
        self.event_message_model.__fields__["type"].validators = [
            typing.cast(ValidatorCallable, self._type_field_validator)
        ]

        self.handlers = {}
        # we need to bind the handlers
        for event, handler in self.__class__.handlers.items():
            # check if handler.method is one of our methods
            if handler.method.__name__ in dir(self) and handler == getattr(
                self, handler.method.__name__
            ):
                self.handlers[event] = MethodType(handler, self)  # type: ignore
            else:
                self.handlers[event] = handler

    def _type_field_validator(
        self, cls: typing.Type[BaseModel], v: typing.Any, *attrs: typing.Any
    ) -> str:
        """
        Validator for type in :attr:`event_message_model`

        Checks if type is a key in :attr:`handlers`
        """
        if v not in self.handlers.keys():
            raise WrongConstantError(given=v, permitted=list(self.handlers.keys()))
        # since self.handlers has only str as keys, we can be sure v is a str
        return typing.cast(str, v)

    @classmethod
    def event(
        cls,
        event: str | typing.Callable | None = None,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> typing.Callable:
        """
        Creates a :class:`Handler` object and attaches it to this class.

        Basically this method just calls :meth:`socketsundso.handler.event` and
        :meth:`attach_handler`.

        .. seealso::
          Takes the same arguments as :meth:.`handler.event`.
        """

        def event_decorator(func: typing.Callable) -> Handler:
            # just call the event decorator defined in handler.py
            handler: Handler = decorator.event(
                event if not callable(event) else None, *args, **kwargs
            )(func)
            cls.attach_handler(handler)
            return handler

        if callable(event):
            return event_decorator(event)
        else:
            return event_decorator

    @classmethod
    def attach_handler(
        cls, handler: Handler, *, overwrite_existing: bool = False
    ) -> None:
        """
        Attach a :class:`.Handler` to this class.

        :raises: :exc:`AssertionError` if a :class:`.Handler` is already attached to
                 :attr:`handler.event` and `overwrite_existing` is ``False``
        """
        assert isinstance(handler, Handler)
        if not overwrite_existing:
            assert (
                handler.event not in cls.handlers
            ), f"duplicate handler for {handler.event}"
        cls.handlers[handler.event] = handler

    async def handle(self, **kwargs: typing.Any) -> EventMessage:
        """
        Calls the appropriate :class:`.Handler` and returns the result
        """
        data = self.event_message_model(**kwargs)
        return await self.handlers[data.type](event_message=data)
