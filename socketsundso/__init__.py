"""socketsundso: A WebSocket JSON API Framework based on FastAPI, pydantic and starlette"""

__version__ = "0.0.3"

from .endpoints import WebSocketHandlingEndpoint as WebSocketHandlingEndpoint
from .handler import on_event as on_event
