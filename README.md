# socketsundso

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

The magical part is that when we receive a message with type 'message' socketsundso will check that all the arguments required are there.

## Documentation
There will propably be some [Sphinx](https://www.sphinx-doc.org/) based documentation at some point. For now you will have to look inside the source files for all the docstrings I wrote.


## Roadmap
Things that should/will/propably won't be implemented soon:

- [x] validation of incoming data (based on type signatures of handlers)
- [ ] response_model
- [ ] nice and shiny documentation
- [ ] examples
- [ ] setup.py etc for easy installation
- [ ] some crazy scheme to make money with this (maybe add a cryptominer to some file deep within?)
- [ ] some kind of license
- [ ] tests!!!
