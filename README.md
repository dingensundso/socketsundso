# socketsundso

**Warning**: This project is in very early development. There is no documentation, no tests, no examples and afaik no users.

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
async def on_message(self, message: str) -> None:
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

You can find some examples in examples/


## Documentation
There will propably be some [Sphinx](https://www.sphinx-doc.org/) based documentation at some point. For now you will have to look inside the source files for all the docstrings I wrote.


## Roadmap
Things that should/will/propably won't be implemented soon:

- [x] validation of incoming data (based on type signatures of handlers)
- [ ] tests!!!
- [x] response_model
- [ ] don't require handlers to be async
- [ ] nice and shiny documentation
- [ ] more examples
- [ ] some crazy scheme to make money with this (maybe add a cryptominer to some file deep within?)
- [x] some kind of license
- [ ] make it compatible with older python versions (at least 3.9, maybe even 3.7)
