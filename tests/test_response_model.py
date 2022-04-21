import typing

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from socketsundso import WebSocketHandlingEndpoint, on_event
from socketsundso.models import WebSocketEventMessage

app = FastAPI()


class ModelWithType(WebSocketEventMessage):
    type = "custom_type"


class ModelWithTypeAndData(WebSocketEventMessage):
    type = "custom_type2"
    data: typing.Dict[str, typing.Any]
    extra_val: int = 42


class SomeData(BaseModel):
    x = 1
    y = 2


class ModelWithSubModel(BaseModel):
    type = "with_submodel"
    data: SomeData


@app.websocket_route("/")
class WSApp(WebSocketHandlingEndpoint):
    @on_event
    async def default_response_model(self):
        return {"message": "hello world"}

    @on_event(response_model=ModelWithType)
    async def response_model_with_type(self):
        return {}

    @on_event(response_model=ModelWithTypeAndData)
    async def response_model_with_type_and_data(self):
        return {"data": {"foobar": 13}}

    @on_event(response_model=ModelWithTypeAndData)
    async def response_model_with_type_and_data_without_data(self):
        return {}

    @on_event(response_model=ModelWithTypeAndData)
    async def response_model_with_type_and_data_override_type(self):
        return {"type": "foobar", "data": {"foobar": 13}}

    @on_event(response_model=ModelWithSubModel)
    async def response_model_wtih_submodel(self):
        return {"data": {}}


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
            "response_model_wtih_submodel",
            {"data": {"x": 1, "y": 2}, "type": "with_submodel"},
        ),
    ],
)
def test_events(event, expected_response):
    with client.websocket_connect("/") as websocket:
        websocket.send_json({"type": event})
        data = websocket.receive_json()
        assert data == expected_response
