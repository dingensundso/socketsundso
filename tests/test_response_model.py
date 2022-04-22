import typing

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from socketsundso import WebSocketHandlingEndpoint, event
from socketsundso.models import EventMessage

app = FastAPI()


class ModelWithType(EventMessage):
    type = "custom_type"


class ModelWithTypeAndData(EventMessage):
    type = "custom_type2"
    data: typing.Dict[str, typing.Any]
    extra_val: int = 42


class SomeData(BaseModel):
    x = 1
    y = 2


class Foo(BaseModel):
    count: int
    size: float = None


class Bar(BaseModel):
    apple = "x"
    banana = "y"


class Spam(BaseModel):
    foo: Foo
    bars: typing.List[Bar]


@app.websocket_route("/")
class WSApp(WebSocketHandlingEndpoint):
    @event
    async def default_response_model(self):
        return {"message": "hello world"}

    @event(response_model=ModelWithType)
    async def response_model_with_type(self):
        return {}

    @event(response_model=ModelWithTypeAndData)
    async def response_model_with_type_and_data(self):
        return {"data": {"foobar": 13}}

    @event(response_model=ModelWithTypeAndData)
    async def response_model_with_type_and_data_without_data(self):
        return {}

    @event(response_model=ModelWithTypeAndData)
    async def response_model_with_type_and_data_override_type(self):
        return {"type": "foobar", "data": {"foobar": 13}}

    @event(response_model=Spam)
    async def response_model_with_submodel(self):
        return dict(foo={"count": 4}, bars=[{"apple": "x1"}, {"apple": "x2"}])


client = TestClient(app)


@pytest.mark.parametrize(
    "event,expected_response",
    [
        (
            "default_response_model",
            {"type": "default_response_model", "message": "hello world"},
        ),
        ("response_model_with_type", {"type": "custom_type"}),
        (
            "response_model_with_type_and_data",
            {"type": "custom_type2", "data": {"foobar": 13}, "extra_val": 42},
        ),
        (
            "response_model_with_type_and_data_without_data",
            {
                "errors": [
                    {
                        "loc": ["response", "data"],
                        "msg": "field required",
                        "type": "value_error.missing",
                    }
                ]
            },
        ),
        (
            "response_model_with_type_and_data_override_type",
            {"type": "foobar", "data": {"foobar": 13}, "extra_val": 42},
        ),
        (
            "response_model_with_submodel",
            {
                "type": "response_model_with_submodel",
                "foo": {"count": 4, "size": None},
                "bars": [
                    {"apple": "x1", "banana": "y"},
                    {"apple": "x2", "banana": "y"},
                ],
            },
        ),
    ],
)
def test_events(event, expected_response):
    with client.websocket_connect("/") as websocket:
        websocket.send_json({"type": event})
        data = websocket.receive_json()
        assert data == expected_response
