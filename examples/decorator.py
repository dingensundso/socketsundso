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

    # use the on_event decorator to register a handler
    @on_event
    async def goodbye(self) -> None:
        # and of course you can reference self
        await self.send_json({"received_at": datetime.now()})
        await self.websocket.close()

    # your handler name can start with on_ or handle_ followed by the event name
    @on_event()
    async def on_message(self, msg: str) -> typing.Dict:
        return {"msg": msg, "type": "reply"}

    # you can even use it for staticmethods
    @on_event
    @staticmethod
    async def time() -> typing.Dict:
        # but of course you won't be able to use self in here
        return {"now": datetime.now()}

    # If you don't want to name your handler like the event it's handling you can give the event
    # name as first argument to the decorator,
    # Other arguments include response_model.
    # For more information about all available arguments, take a look at the documentation and/or
    # code.
    @on_event("ping", response_model=Pong)
    async def pingpong(self) -> typing.Dict:
        return {"time": datetime.now()}


# if you want to register a function outside of the class you have to use the on_event decorator
# of the class. Of course you can also use all arguments with this one.
@MyWebSocketApp.on_event("echo", response_model=EchoMessage)
async def outside(message: str) -> typing.Dict:
    return {"message": message}
