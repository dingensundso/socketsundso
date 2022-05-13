"""socketsundso: A WebSocket JSON API Framework based on FastAPI, pydantic and starlette"""

__version__ = "0.0.6.dev2"

from .decorator import event as event
from .endpoints import WebSocketHandlingEndpoint as WebSocketHandlingEndpoint
