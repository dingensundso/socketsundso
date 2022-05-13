import random

import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient

from socketsundso import WebSocketHandlingEndpoint, event

from .test_decorators import WSApp, app

random.seed(42)


@app.websocket("/random")
class RandomWSApp(WebSocketHandlingEndpoint):
    def __init__(self, websocket: WebSocket):
        super().__init__(websocket)
        self.random_value = random.random()

    @event
    async def rand(self):
        return {"value": self.random_value}


client = TestClient(app)


def test_rand():
    with client.websocket_connect("/random") as websocket:
        websocket.send_json({"type": "rand"})
        data = websocket.receive_json()
        assert data == {"type": "rand", "value": 0.6394267984578837}


def test_different_instances():
    client2 = TestClient(app)
    with client.websocket_connect("/random") as websocket:
        with client2.websocket_connect("/random") as websocket2:
            websocket2.send_json({"type": "rand"})
            data2 = websocket2.receive_json()
        websocket.send_json({"type": "rand"})
        data = websocket.receive_json()
    assert data != data2
    assert data == {"type": "rand", "value": 0.025010755222666936}
    assert data2 == {"type": "rand", "value": 0.27502931836911926}


@app.websocket("/app2")
class WSApp2(WSApp):
    @event
    def decorator_without_parantheses(self):
        return {"type": "overwritten"}

    @event("decorator_with_parentheses_event")
    async def decorator_with_parantheses_and_event2(self):
        return {"type": "overwritten"}


@pytest.mark.parametrize(
    "event,expected_response",
    [
        ("decorator_without_parantheses", {"type": "overwritten"}),
        ("decorator_with_parentheses_event", {"type": "overwritten"}),
    ],
)
def test_overwritten(event, expected_response):
    with client.websocket_connect("/app2") as websocket:
        websocket.send_json({"type": event})
        data = websocket.receive_json()
        assert data == expected_response


@pytest.mark.parametrize(
    "event,expected_response",
    [
        ("decorator_with_parantheses", {"type": "hello_world"}),
        ("class_decorator_without_parantheses", {"type": "hello_world"}),
        ("class_decorator_with_parantheses", {"type": "hello_world"}),
        ("class_decorator_with_parentheses_event", {"type": "hello_world"}),
        ("function_without_decorator", {"type": "hello_world"}),
        ("function_without_decorator_event", {"type": "hello_world"}),
        ("decorator_outside_class_attached", {"type": "hello_world"}),
        ("static_method", {"type": "hello_world"}),
    ],
)
def test_subclass(event, expected_response):
    with client.websocket_connect("/app2") as websocket:
        websocket.send_json({"type": event})
        data = websocket.receive_json()
        assert data == expected_response

    @app.websocket("/app3")
    class WSApp3(WSApp2):
        pass

    with client.websocket_connect("/app3") as websocket:
        websocket.send_json({"type": event})
        data = websocket.receive_json()
        assert data == expected_response


def test_overwrite_existing_false():
    with pytest.raises(AssertionError):

        class WSApp3(WSApp2, overwrite_existing=False):
            @event
            def decorator_without_parantheses(self):
                return {"type": "foobar"}


def test_overwrite_existing_true():
    @app.websocket("/app4")
    class WSApp3(WSApp2, overwrite_existing=True):
        @event
        def decorator_without_parantheses(self):
            return {"type": "foobar"}

    with client.websocket_connect("/app4") as websocket:
        websocket.send_json({"type": "decorator_without_parantheses"})
        data = websocket.receive_json()
        assert data == {"type": "foobar"}


def test_overwrite_existing_doubly():
    with pytest.raises(AssertionError):

        class WSApp3(WSApp2, overwrite_existing=True):
            @event("overwrite_me")
            def method1(self):
                return {"type": "foobar"}

            @event("overwrite_me")
            def method2(self):
                return {"type": "foobar"}
