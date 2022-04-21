import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from socketsundso import WebSocketHandlingEndpoint, on_event

app = FastAPI()


@app.websocket_route("/")
class WSApp(WebSocketHandlingEndpoint):
    @on_event
    async def decorator_without_parantheses(self):
        return {"type": "hello_world"}

    @on_event()
    async def decorator_with_parantheses(self):
        return {"type": "hello_world"}

    @on_event("decorator_with_parentheses_event")
    async def decorator_with_parantheses_and_event(self):
        return {"type": "hello_world"}


@WSApp.on_event
async def class_decorator_without_parantheses():
    return {"type": "hello_world"}


@WSApp.on_event()
async def class_decorator_with_parantheses():
    return {"type": "hello_world"}


@WSApp.on_event("class_decorator_with_parentheses_event")
async def class_decorator_with_parantheses_and_event():
    return {"type": "hello_world"}


client = TestClient(app)


@pytest.mark.parametrize(
    "event,expected_response",
    [
        ("decorator_without_parantheses", {"type": "hello_world"}),
        ("decorator_with_parantheses", {"type": "hello_world"}),
        ("decorator_with_parentheses_event", {"type": "hello_world"}),
        ("class_decorator_without_parantheses", {"type": "hello_world"}),
        ("class_decorator_with_parantheses", {"type": "hello_world"}),
        ("class_decorator_with_parentheses_event", {"type": "hello_world"}),
    ],
)
def test_events(event, expected_response):
    with client.websocket_connect("/") as websocket:
        websocket.send_json({"type": event})
        data = websocket.receive_json()
        assert data == expected_response


@pytest.mark.parametrize(
    "event",
    [
        ("decorator_with_parantheses_and_event"),
        ("class_decorator_with_parantheses_and_event"),
        ("nonexistant"),
    ],
)
def test_nonexistant_events(event):
    with client.websocket_connect("/") as websocket:
        websocket.send_json({"type": event})
        data = websocket.receive_json()
        assert "errors" in data
        assert data["errors"][0]["ctx"]["given"] == event
