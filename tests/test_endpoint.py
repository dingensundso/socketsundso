import random

from fastapi import FastAPI
from fastapi.testclient import TestClient

from socketsundso import WebSocketHandlingEndpoint, event

app = FastAPI()
random.seed(42)


@app.websocket_route("/")
class WSApp(WebSocketHandlingEndpoint):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.random_value = random.random()

    @event
    async def rand(self):
        return {"value": self.random_value}


client = TestClient(app)


def test_rand():
    with client.websocket_connect("/") as websocket:
        websocket.send_json({"type": "rand"})
        data = websocket.receive_json()
        assert data == {"type": "rand", "value": 0.6394267984578837}


def test_different_instances():
    client2 = TestClient(app)
    with client.websocket_connect("/") as websocket:
        with client2.websocket_connect("/") as websocket2:
            websocket2.send_json({"type": "rand"})
            data2 = websocket2.receive_json()
        websocket.send_json({"type": "rand"})
        data = websocket.receive_json()
    assert data != data2
    assert data == {"type": "rand", "value": 0.025010755222666936}
    assert data2 == {"type": "rand", "value": 0.27502931836911926}
