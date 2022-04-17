""":mod:`pydantic` models used in this project"""
from pydantic import BaseModel


class WebSocketEventMessage(BaseModel):
    """
    BaseModel of an incoming WebSocketEvent

    All other arguments of a handler will be added dynamically.

    .. note:: When validating incoming messages, type will be replaced with a
              :class:`typing.Literal` for all registered event types.
              So basically this whole class is kind of pointless.
    """

    type: str

    class Config:
        use_enum_values = True
        extra = "allow"
