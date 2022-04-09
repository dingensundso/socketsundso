""":module:`pydantic` models used in this project"""
import typing

from pydantic import BaseModel

class WebSocketEventMessage(BaseModel):
    """
    BaseModel of an incoming WebSocketEvent

    All other arguments of a handler will be added dynamically.

    Note: When validating incoming messages, type will be replaced with an :class:`enum.Enum` of
    all registered event types.
    """
    type: str
#    data: typing.Any

    class Config:
        use_enum_values = True
        extra = 'allow'
