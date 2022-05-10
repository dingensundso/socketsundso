"""socketsundso: A WebSocket JSON API Framework based on FastAPI, pydantic and starlette"""

__version__ = "0.0.6.dev2"

from .endpoints import WebSocketHandlingEndpoint as WebSocketHandlingEndpoint
from .handler import event as event
