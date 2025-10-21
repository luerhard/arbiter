# core/discuss/room_state.py
from collections.abc import Awaitable
from collections.abc import Callable
import json
import logging
import os
from typing import Any

from redis.asyncio import Redis
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
        "online_users": [],
        "required_users": [],
        "page": 0,
        "discussion_ended": False,
        "cur_example_id": 0,
        "cur_example": "",
        "annotation_labels": {},
        "discussion_labels": {},
        "clicked_done": {},  # {username: 0|1}
        "messages": [],  # dict-keys: username, msg
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
