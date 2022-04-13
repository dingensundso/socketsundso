"""socketsundso: A WebSocket JSON API Framework based on FastAPI, pydantic and starlette"""

__version__ = "0.0.1"

from .endpoints import WebSocketHandlingEndpoint
from .handler import on_event
