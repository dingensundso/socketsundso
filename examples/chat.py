import typing

from fastapi import FastAPI, WebSocket
from fastapi.encoders import jsonable_encoder
from pydantic.error_wrappers import ErrorWrapper, ValidationError

from socketsundso import WebSocketHandlingEndpoint, on_event
from socketsundso.models import WebSocketEventMessage

app = FastAPI()


# models
class ChatMessage(WebSocketEventMessage):
    type = "message"
    sender: int | None
    msg: str


class BroadcastMessage(ChatMessage):
    pass


# classes
class Client:
    def __init__(self, client_id: int, websocket: WebSocket):
        self.id = client_id
        self.websocket = websocket

    async def send_json(self, data: typing.Any) -> None:
        await self.websocket.send_json(jsonable_encoder(data))


class ChatRoom:
    def __init__(self, room_id: str) -> None:
        self.id = room_id
        self.clients: typing.List[Client] = []

    async def connect(self, client: Client) -> None:
        self.clients.append(client)
        await client.websocket.accept()
        await self.broadcast({"type": "join", "client_id": client.id})

    async def disconnect(self, client: Client) -> None:
        self.clients.remove(client)
        await self.broadcast({"type": "leave", "client_id": client.id})

    async def broadcast(self, message: WebSocketEventMessage | typing.Dict) -> None:
        if isinstance(message, dict):
            message = WebSocketEventMessage(**message)
        for client in self.clients:
            await client.send_json(message)


rooms: typing.Dict[str, ChatRoom] = {}


@app.websocket_route("/room/{room_id:str}/{client_id:int}")
class MyChatApp(WebSocketHandlingEndpoint):
    client: Client
    room: ChatRoom

    async def on_connect(self) -> None:
        client_id = self.websocket.path_params["client_id"]
        self.client = Client(client_id, self.websocket)
        room_id = self.websocket.path_params["room_id"]

        room = rooms.get(room_id)
        # create room if it doesn't exist
        if room is None:
            room = ChatRoom(room_id)
            rooms[room_id] = room
        self.room = room
        # connect to room
        await self.room.connect(self.client)

    async def on_disconnect(self, close_code: int) -> None:
        await self.room.disconnect(self.client)
        if len(self.room.clients) == 0:
            del rooms[self.room.id]

    @on_event(response_model=BroadcastMessage)
    async def on_message(self, msg: str) -> typing.Dict:
        return {"msg": msg, "sender": self.client.id}

    async def on_whisper(self, to: int, msg: str) -> None:
        recipient = next(
            (client for client in self.room.clients if client.id == to), None
        )
        if recipient is None:
            raise ValidationError(
                [ErrorWrapper(exc=ValueError("recipient not found"), loc=("to",))],
                self.handlers["message"].model,
            )
        else:
            await recipient.send_json(
                {"type": "whisper", "from": self.client.id, "msg": msg}
            )

    async def send_json(self, response: typing.Any) -> None:
        # check type of response and act accordingly
        if isinstance(response, BroadcastMessage):
            return await self.room.broadcast(response)
        else:
            return await self.client.send_json(response)
