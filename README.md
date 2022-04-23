# socketsundso

**Warning**: This project is in very early development.

## What's all this then?
This is an opionated framework for creating WebSocket APIs based on [FastAPI](https://fastapi.tiangolo.com/), [Starlette](https://www.starlette.io/) and [pydantic](https://pydantic-docs.helpmanual.io/).
FastAPI offers nice validation (powered by pydantic) for HTTP endpoints. This framework tries to make it easy to use all these goodies when develooping a JSON based websocket API.

## Concept
The whole idea is based around the concept of a simple json based protocol. Messages between client and server can be categorized by a type or event and contain some data.
For HTTP the type/event will mostly be conveyed via path or querystring. When using WebSockets you could also use the path for this but this would mean opening a new socket for every type of event. Seems unnecassery when you already have a perfectly working connection established.

### Message Format
The basic message format is as follows
```python
{
	type: str,
	...
}
```

Seems simple. Doesn't it? Well here comes the magic: Let's assume we want to build something similar to a chat application where users can send messages. So we would have an event called message. In our application we can simply define a handler for it and this awesome framework will call the handler whenever it receives a message with the type 'message'.

```python
@on_event
def on_message(self, message: str) -> None:
	print('Hey i just received a message:')
	print(message)
```

When registering a handler like above, socketsundso will create a pydantic model specifically for messages for this handler.
This model is similar to this:
```python
class Message(BaseModel):
	type: typing.Literal('message'),
	message: str

	class Config:
		extra = 'forbid'
```

The response will also be validated through a model. But since it's hard to guess what you want in your output you have to give a response_model. Otherwise socketsundso will just make sure there is a type in the response.
For more information take a look at the documentation.

## Documentation
The documentation is located at <https://socketsundso.dingensundso.de>.
You can also find some examples in examples/


## Roadmap
Things that should/will/propably won't be implemented soon:

- [x] validation of incoming data (based on type signatures of handlers)
- [x] tests!!!
- [x] response_model
- [x] don't require handlers to be async
- [x] nice and shiny documentation
- [ ] more and better examples
- [ ] some crazy scheme to make money with this (maybe add a cryptominer to some file deep within?)
- [x] some kind of license
- [ ] make it compatible with older python versions (at least 3.9, maybe even 3.7)
- [ ] more and better tests
- [ ] more and better documentation
