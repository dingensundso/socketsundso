"""socketsundso: A WebSocket JSON API Framework based on FastAPI, pydantic and starlette"""

__version__ = "0.0.6.dev1"

from .endpoints import (
    StarletteWebSocketHandlingEndpoint as StarletteWebSocketHandlingEndpoint,
)
from .endpoints import WebSocketHandlingEndpoint as WebSocketHandlingEndpoint
from .handler import event as event
