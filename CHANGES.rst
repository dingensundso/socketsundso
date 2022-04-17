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
