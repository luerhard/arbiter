# core/discuss/room_state.py
from collections.abc import Awaitable
from collections.abc import Callable
import json
import logging
import os
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from redis import Redis as SyncRedis
from redis.asyncio import Redis
from redis.exceptions import RedisError
from redis.exceptions import WatchError

log = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
_redis: Redis | None = None


def _r() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(REDIS_URL, decode_responses=True)
    return _redis


def _key(batch_id: int | str) -> str:
    log.debug(f"room:{batch_id}")
    return f"room:{batch_id}"


def _defaults() -> dict[str, Any]:
    return {
        "version": 0,
        "online_users": [],  # users with at least one open connection
        "connections": {},  # {username: [channel names]}
        "required_users": [],
        "page": 0,
        "discussion_ended": False,
        "cur_example_id": 0,
        "cur_example": "",
        "annotation_labels": {},
        "discussion_labels": {},
        "clicked_done": {},  # {username: 0|1}, a saved decision for the current example
        "saving_example": None,  # example whose decisions are being written to the database
        "messages": [],  # dict-keys: username, msg
        "total_pages": 0,
    }


async def get_state(batch_id: int | str) -> dict[str, Any]:
    raw = await _r().get(_key(batch_id))
    log.debug(f"{raw = }")
    return json.loads(raw) if raw else _defaults()


async def set_state(batch_id: int | str, state: dict[str, Any]) -> dict[str, Any]:
    # bump version and persist
    state["version"] = int(state.get("version", 0)) + 1
    await _r().set(_key(batch_id), json.dumps(state))
    return state


async def update_state(
    batch_id: int | str,
    mut: Callable[[dict[str, Any]], Awaitable[dict[str, Any]] | dict[str, Any]],
) -> dict[str, Any]:
    """Atomic-ish update using WATCH/MULTI/EXEC."""
    r = _r()
    k = _key(batch_id)
    while True:
        try:
            async with r.pipeline(transaction=True) as p:
                await p.watch(k)
                cur = await r.get(k)
                state = json.loads(cur) if cur else _defaults()
                new_state = await mut(state) if callable(mut) else state  # type: ignore
                new_state["version"] = int(new_state.get("version", 0)) + 1
                p.multi()
                p.set(k, json.dumps(new_state))
                await p.execute()
                return new_state
        except WatchError:
            # state changed between WATCH and EXEC, retry
            continue


def close_room(batch_id: int | str, phase: str) -> None:
    """Tell the clients in a room that the batch left the discussion phase. A failing
    channel layer must not block the phase change."""
    try:
        async_to_sync(get_channel_layer().group_send)(
            f"chat_{batch_id}",
            {"type": "room_closed", "phase": phase},
        )
    except Exception:
        log.warning("Could not close the chat room of batch %s", batch_id, exc_info=True)


def delete_state(batch_id: int | str) -> None:
    """Forget the chat state of a deleted batch. A Redis outage must not block the deletion."""
    try:
        with SyncRedis.from_url(REDIS_URL) as r:
            r.delete(_key(batch_id))
    except RedisError:
        log.warning("Could not delete the chat state of batch %s", batch_id, exc_info=True)


def delete_all_states() -> int:
    """Forget the chat state of every batch, e.g. after the database was reset."""
    with SyncRedis.from_url(REDIS_URL) as r:
        keys = list(r.scan_iter(_key("*")))
        return r.delete(*keys) if keys else 0
