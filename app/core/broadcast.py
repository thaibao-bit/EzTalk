"""Redis-backed broadcaster for cross-worker WebSocket coordination."""

from typing import Any
import json

from broadcaster import Broadcast
from app.core.config import settings


broadcast = Broadcast(settings.redis_url)


def session_channel(session_id: str) -> str:
    """Return the Redis Pub/Sub channel for a chat session."""

    return f"chat.session.{session_id}"


async def connect_broadcast() -> None:
    """Connect to Redis Pub/Sub when enabled."""

    if settings.redis_broadcast_enabled:
        await broadcast.connect()


async def disconnect_broadcast() -> None:
    """Disconnect from Redis Pub/Sub when enabled."""

    if settings.redis_broadcast_enabled:
        await broadcast.disconnect()


async def publish_session_event(session_id: str, event: dict[str, Any]) -> None:
    """Publish a WebSocket event for cross-replica session coordination."""

    if settings.redis_broadcast_enabled:
        await broadcast.publish(
            channel=session_channel(session_id),
            message=json.dumps(event, ensure_ascii=False),
        )


async def subscribe_session_events(session_id: str):
    """Subscribe to cross-replica events for one session."""

    async with broadcast.subscribe(channel=session_channel(session_id)) as subscriber:
        async for event in subscriber:
            yield _decode_event(event)


def _decode_event(event: Any) -> dict[str, Any]:
    message = event.message
    if isinstance(message, bytes):
        message = message.decode("utf-8")
    return json.loads(message)
