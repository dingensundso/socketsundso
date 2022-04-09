from typing import Dict

from fastapi import FastAPI

from socketsundso import WebSocketHandlingEndpoint, on_event

app = FastAPI()

@app.websocket_route("/ws")
class MyWSApp(WebSocketHandlingEndpoint):
    # will be automatically set as handler for message
    async def on_message(self, msg: str) -> Dict:
        return {'msg':msg}

    # alternatively you can use the on_event decorator
    @on_event('foobar')
    async def somemething(self) -> None:
        # and of course you can reference self
        await self.send_json({'foo': 'bar'})

# if you want to register a function outside of the class you have to use the on_event decorator
# of the class.
@MyWSApp.on_event('barbaz')
async def outside() -> Dict:
    return {'bar':'baz'}
