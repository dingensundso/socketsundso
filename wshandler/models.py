""":module:`pydantic` models used in this project"""
import typing

from pydantic import BaseModel

class WebsocketEventMessage(BaseModel):
    """BaseModel of an incoming WebsocketEvent"""
    type: str
    data: typing.Any
