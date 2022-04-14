"""
Smallish example showing how the different decorators may be used
"""
import typing
from datetime import datetime

from fastapi import FastAPI
from pydantic import BaseModel

from socketsundso import WebSocketHandlingEndpoint, on_event

# first we create the fasapi app as usual
app = FastAPI()


# Then we create some models
class Pong(BaseModel):
    # we set the type
    type: str = "pong"
    # and define everything that should be included
    time: datetime


class EchoMessage(BaseModel):
    type: str = "echo"
    message: str


# let's mount our endpoint to fastapi
@app.websocket_route("/")
class MyWebSocketApp(WebSocketHandlingEndpoint):
    # methods starting with on_ will be automatically registered as handler
    # in this case for type 'message'
    async def on_message(self, msg: str) -> typing.Dict:
        return {"msg": msg, "type": "reply"}

    # alternatively you can use the on_event decorator
    @on_event("goodbye")
    async def goodbye(self) -> None:
        # and of course you can reference self
        await self.send_json({"received_at": datetime.now()})
        await self.websocket.close()

    # you can even use it for staticmethods
    @on_event("time")
    @staticmethod
    async def time() -> typing.Dict:
        # but of course you won't be able to use self in here
        return {"now": datetime.now()}

    # you can set the response_model with the decorator
    @on_event("ping", response_model=Pong)
    async def pingpong(self) -> typing.Dict:
        return {"time": datetime.now()}


# if you want to register a function outside of the class you have to use the on_event decorator
# of the class. Of course you can also use response_model with this one.
@MyWebSocketApp.on_event("echo", response_model=EchoMessage)
async def outside(message: str) -> typing.Dict:
    return {"message": message}
