class EventNotFound(TypeError):
    """
    Raised when no handler can be found for received :attr:`WebsocketEventMessage.type`
    """
    pass
