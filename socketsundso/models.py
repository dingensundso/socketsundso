"""
Like `FastAPI <https:fastapi.tiangolo.com>`_ :mod:`socketsundso` makes heavy use of `pydantic
<https://pydantic-docs.helpmanual.io/>`_ models.

Every message exchanged between client and server has to be some subtype of
:class:`EventMessage`.
That means there has to be at least a :attr:`.type` and there can be a whole lot of data.

The :attr:`.type` is how client and server decide what to do with everything also inside the object.
In the case of :mod:`socketsundso` we will call a :class:`.Handler` that is registered in our
:class:`.WebSocketHandlingEndpoint` for that type.
"""
from pydantic import BaseModel


class EventMessage(BaseModel):
    """
    BaseModel of an incoming or outgoing Event

    Most of the time when this class is used it's just the base for another model. The models
    are created dynamically at different places in different classes.

    E.g. :class:`.WebSocketHandlingEndpoint` creates a model based on this one but
    replaces the type for :attr:`type` with a :class:`typing.Literal` with all the registered
    events.

    :class:`.Handler` creates a model for incoming data based on this model and the signature of
    the handler function.
    """

    type: str

    class Config:
        """
        :meta private:
        """

        use_enum_values = True
        extra = "allow"
