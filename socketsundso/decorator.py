import typing

from pydantic import BaseModel

from .handler import Handler


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
