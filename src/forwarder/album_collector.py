"""
MediaGroup / Album Collector
----------------------------
Asynchronous debounce buffer for collecting Telegram Media Groups (albums).
Bundles grouped messages sharing the same `grouped_id` and dispatches them
together in a single batch.
"""

import asyncio
import logging
from typing import Callable, Dict, Any, List

logger = logging.getLogger(__name__)


class MediaGroupCollector:
    """Collects and debounces incoming Telegram album messages."""

    def __init__(self, debounce_seconds: float = 1.2):
        self.debounce_seconds = debounce_seconds
        self._groups: Dict[int, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def is_grouped(message) -> bool:
        """Check if message is part of an album / media group."""
        return bool(getattr(message, "grouped_id", None))

    async def add_message(
        self,
        message,
        source_id,
        targets: list,
        rule: dict,
        on_complete: Callable[[Dict[str, Any]], Any]
    ) -> bool:
        """
        Add a message to the group buffer.
        Returns True if message was enqueued into an album, False if it is a standalone post.
        """
        grouped_id = getattr(message, "grouped_id", None)
        if not grouped_id:
            return False

        async with self._lock:
            if grouped_id not in self._groups:
                self._groups[grouped_id] = {
                    "grouped_id": grouped_id,
                    "messages": [],
                    "source_id": source_id,
                    "targets": targets,
                    "rule": rule,
                    "timer_task": None,
                }

            group_data = self._groups[grouped_id]
            # Avoid duplicate message IDs inside the same album buffer
            existing_ids = {getattr(m, "id", None) for m in group_data["messages"]}
            if getattr(message, "id", None) not in existing_ids:
                group_data["messages"].append(message)

            # Cancel existing debounce timer to reset the window
            if group_data["timer_task"] and not group_data["timer_task"].done():
                group_data["timer_task"].cancel()

            # Schedule new debounce timer
            group_data["timer_task"] = asyncio.create_task(
                self._wait_and_flush(grouped_id, on_complete)
            )

        return True

    async def _wait_and_flush(self, grouped_id: int, on_complete: Callable):
        """Wait for the debounce interval then flush all collected messages in the album."""
        try:
            await asyncio.sleep(self.debounce_seconds)
        except asyncio.CancelledError:
            return

        async with self._lock:
            group_data = self._groups.pop(grouped_id, None)

        if group_data and group_data["messages"]:
            try:
                # Sort messages in the album by message ID in chronological order
                group_data["messages"].sort(key=lambda m: getattr(m, "id", 0))
                await on_complete(group_data)
            except Exception as e:
                logger.error(f"Error executing album dispatch callback for group {grouped_id}: {e}")

    async def clear(self):
        """Cancel all pending album timers and clear buffers."""
        async with self._lock:
            for group_data in self._groups.values():
                task = group_data.get("timer_task")
                if task and not task.done():
                    task.cancel()
            self._groups.clear()
