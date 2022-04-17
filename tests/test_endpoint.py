from fastapi import FastAPI
from fastapi.testclient import TestClient

from socketsundso import WebSocketHandlingEndpoint, on_event

app = FastAPI()


@app.websocket_route("/")
class WSApp(WebSocketHandlingEndpoint):
    @on_event
    async def on_echo(self, msg: str):
        return {"msg": msg}


def test_echo_handler():
    client = TestClient(app)
    with client.websocket_connect("/") as websocket:
        websocket.send_json({"type": "echo", "msg": "foobar"})
        data = websocket.receive_json()
        assert data == {"type": "echo", "msg": "foobar"}
