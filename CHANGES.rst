Version 0.0.6
-------------

Unreleased

Breaking Changes
^^^^^^^^^^^^^^^^

- make :class:`.WebSocketHandlingEndpoint` FastAPI router compatible (removes starlette router compability)

Changes
^^^^^^^

- fix calling of :class:`.Handler` with not async method
- add :class:`.StarletteWebSocketHandlingEndpoint`


Version 0.0.5
-------------

Changes
^^^^^^^

- :class:`.Handler`: if we didn't get a :attr:`.response_model` but :attr:`method` returns a model use it
- if :class:`.Handler.__call__` receives :class:`.EventMessage` as only argument (ignoring implicit self), call :meth:`.Handler.handle_event`
- :class:`.WebSocketHandlingEndpoint` creates :attr:`.handlers` for each instance and binds :class:`Handler` s
- :class:`.WebSocketHandlingEndpoint` uses :meth:`.Handler.__call__` instead of :meth:`.Handler.handle_event`
- :meth:`.Handler.handle_event` has optional method attribute (used by __call__ if :class:`.Handler` is called with implicit self and :class:`.EventMessage`)
- :attr:`.Handler.method` no longer has to be a coroutine

Version 0.0.4
-------------

Breaking changes
^^^^^^^^^^^^^^^^

- rename :class:`.WebSocketEventMessage` to :class:`.EventMessage`
- remove :meth:`.WebSocketHandlingEndpoint.on_receive`
- replace :meth:`.WebSocketHandlingEndpoint.send_json` with :meth:`.WebSocketHandlingEndpoint.respond`
- rename :meth:`.Handler.handle` to :meth:`.Handler.handle_event`
- rename :meth:`socketsundso.handler.on_event` to :meth:`socketsundso.handler.event`
- rename :meth:`.WebSocketHandlingEndpoint.on_event` to :meth:`.WebSocketHandlingEndpoint.event`

Other changes
^^^^^^^^^^^^^

- reintroduce :meth:`.WebSocketHandlingEndpoint.attach_handler`
- make :meth:`.WebSocketHandlingEndpoint.on_event` (like it was supposed to be)
- move event name generation from :meth:`.on_event` decorator to :meth:`.Handler.__init__`

Version 0.0.3
-------------

Released on 2022-04-17


Breaking changes
^^^^^^^^^^^^^^^^

- removed implicit handler generation
    all handlers have to be decorated with :meth:`.on_event` or :meth:`.WebSocketHandlingEndpoint.on_event`


Other changes
^^^^^^^^^^^^^

- rework of on_event deocrators

  - make event parameter optional (methodname will be used without leading :meth:`on\_` or :meth:`handle\_`)
  - can be used without parentheses

- removed upper bounds for dependencies
    we can't know when shit will break


Additions
^^^^^^^^^

- new example: chat.py
- Documentation
