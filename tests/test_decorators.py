import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from socketsundso import WebSocketHandlingEndpoint, event
from socketsundso.handler import Handler

app = FastAPI()


@app.websocket("/")
class WSApp(WebSocketHandlingEndpoint):
    @event
    def decorator_without_parantheses(self):
        return {"type": "hello_world"}

    @event()
    async def decorator_with_parantheses(self):
        return {"type": "hello_world"}

    @event("decorator_with_parentheses_event")
    async def decorator_with_parantheses_and_event(self):
        return {"type": "hello_world"}

    @event
    @staticmethod
    async def static_async_method():
        return {"type": "hello_world"}

    @event
    @staticmethod
    def static_method():
        return {"type": "hello_world"}

    @event
    async def async_with_arg(self, msg: str):
        return {"reply": msg}

    @event
    def with_arg(self, msg: str):
        return {"reply": msg}


@WSApp.event
async def class_decorator_without_parantheses():
    return {"type": "hello_world"}


@WSApp.event()
async def class_decorator_with_parantheses():
    return {"type": "hello_world"}


@WSApp.event("class_decorator_with_parentheses_event")
async def class_decorator_with_parantheses_and_event():
    return {"type": "hello_world"}


@event
async def decorator_outside_class():
    return {"type": "hello_world"}


@event
async def decorator_outside_class_attached():
    return {"type": "hello_world"}


async def function_without_decorator():
    return {"type": "hello_world"}


WSApp.attach_handler(decorator_outside_class_attached)
WSApp.attach_handler(Handler(method=function_without_decorator))
WSApp.attach_handler(
    Handler(event="function_without_decorator_event", method=function_without_decorator)
)


@app.websocket("/app2")
class WSApp2(WSApp):
    @event
    def decorator_without_parantheses(self):
        return {"type": "overwritten"}

    @event("decorator_with_parentheses_event")
    async def decorator_with_parantheses_and_event2(self):
        return {"type": "overwritten"}


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
        ("function_without_decorator", {"type": "hello_world"}),
        ("function_without_decorator_event", {"type": "hello_world"}),
        ("decorator_outside_class_attached", {"type": "hello_world"}),
        ("static_method", {"type": "hello_world"}),
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
        ("decorator_outside_class"),
    ],
)
def test_nonexistant_events(event):
    with client.websocket_connect("/") as websocket:
        websocket.send_json({"type": event})
        data = websocket.receive_json()
        assert "errors" in data
        assert data["errors"][0]["ctx"]["given"] == event


@pytest.mark.parametrize(
    "event,args,expected_response",
    [
        (
            "async_with_arg",
            {"msg": "foobar"},
            {"type": "async_with_arg", "reply": "foobar"},
        ),
        ("with_arg", {"msg": "foobar"}, {"type": "with_arg", "reply": "foobar"}),
    ],
)
def test_with_param(event, args, expected_response):
    with client.websocket_connect("/") as websocket:
        websocket.send_json({"type": event, **args})
        data = websocket.receive_json()
        assert data == expected_response


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


def test_overwrite_existing_false():
    with pytest.raises(AssertionError):

        class WSApp3(WSApp2, overwrite_existing=False):
            @event
            def decorator_without_parantheses(self):
                return {"type": "foobar"}


def test_overwrite_existing_true():
    @app.websocket("/app3")
    class WSApp3(WSApp2, overwrite_existing=True):
        @event
        def decorator_without_parantheses(self):
            return {"type": "foobar"}

    with client.websocket_connect("/app3") as websocket:
        websocket.send_json({"type": "decorator_without_parantheses"})
        data = websocket.receive_json()
        assert data == {"type": "foobar"}


def test_overwrite_existing_doubly():
    with pytest.raises(AssertionError):

        @app.websocket("/app3")
        class WSApp3(WSApp2, overwrite_existing=True):
            @event("overwrite_me")
            def method1(self):
                return {"type": "foobar"}

            @event("overwrite_me")
            def method2(self):
                return {"type": "foobar"}
