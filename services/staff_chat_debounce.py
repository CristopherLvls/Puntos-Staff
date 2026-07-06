"""Anti-spam por debounce: agrupa mensajes y responde tras una pausa."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import discord

logger = logging.getLogger("insight_ia.debounce")

BatchCallback = Callable[[list[discord.Message]], Awaitable[None]]


@dataclass
class _PendingBatch:
    messages: list[discord.Message] = field(default_factory=list)
    task: asyncio.Task | None = None


class StaffChatDebouncer:
    def __init__(
        self,
        callback: BatchCallback,
        delay_seconds: float,
        max_calls_per_minute: int,
    ):
        self._callback = callback
        self._delay = delay_seconds
        self._max_per_minute = max_calls_per_minute
        self._pending: dict[str, _PendingBatch] = {}
        self._api_calls: dict[int, list[float]] = {}

    def _batch_key(self, message: discord.Message) -> str:
        if isinstance(message.channel, discord.DMChannel):
            return f"dm:{message.author.id}"
        return f"{message.channel.id}:{message.author.id}"

    def _is_rate_limited(self, user_id: int) -> bool:
        now = time.monotonic()
        window = self._api_calls.setdefault(user_id, [])
        window[:] = [t for t in window if now - t < 60]
        return len(window) >= self._max_per_minute

    def _record_call(self, user_id: int) -> None:
        self._api_calls.setdefault(user_id, []).append(time.monotonic())

    async def add(self, message: discord.Message) -> bool:
        """Encola un mensaje. Devuelve False si el usuario superó el rate limit."""
        user_id = message.author.id
        if self._is_rate_limited(user_id):
            return False

        key = self._batch_key(message)
        batch = self._pending.setdefault(key, _PendingBatch())
        batch.messages.append(message)

        if batch.task and not batch.task.done():
            batch.task.cancel()

        batch.task = asyncio.create_task(self._flush_later(key, user_id))
        return True

    async def _flush_later(self, key: str, user_id: int) -> None:
        try:
            await asyncio.sleep(self._delay)
            batch = self._pending.pop(key, None)
            if not batch or not batch.messages:
                return
            self._record_call(user_id)
            await self._callback(batch.messages)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Error procesando batch de chat staff (key=%s)", key)
