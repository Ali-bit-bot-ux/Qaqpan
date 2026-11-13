import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Any

logger = logging.getLogger("qaqpan.events")


class EventBus:
    """
    In-memory async pub/sub event bus for Server-Sent Events (SSE).
    Notifies connected frontend clients in real time when transfer state changes.
    """
    def __init__(self):
        self._subscribers: set[asyncio.Queue] = set()

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(q)
        logger.info(f"New SSE client connected. Total clients: {len(self._subscribers)}")
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)
        logger.info(f"SSE client disconnected. Total clients: {len(self._subscribers)}")

    async def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        message = {
            "event": event_type,
            "data": data
        }
        for q in list(self._subscribers):
            try:
                q.put_nowait(message)
            except Exception as e:
                logger.warning(f"Failed to deliver event to subscriber: {e}")


event_bus = EventBus()

