import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

logger = logging.getLogger(__name__)

_Registration = tuple[float, Callable[[], Coroutine[Any, Any, None]]]


class BackgroundScheduler:
    def __init__(self) -> None:
        self._registrations: list[_Registration] = []
        self._tasks: dict[str, asyncio.Task[Any]] = {}

    def register(
        self,
        interval_seconds: float,
        task: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        self._registrations.append((interval_seconds, task))

    def start(self) -> None:
        for interval_seconds, task in self._registrations:
            name = getattr(task, "__name__", str(id(task)))
            t = asyncio.create_task(self._run_periodic(interval_seconds, task, name))
            self._tasks[name] = t
            logger.info("Scheduled task %s every %ss", name, interval_seconds)

    async def _run_periodic(
        self,
        interval_seconds: float,
        task: Callable[[], Coroutine[Any, Any, None]],
        name: str,
    ) -> None:
        while True:
            try:
                await task()
            except Exception:
                logger.exception("Background task %s failed", name)
            await asyncio.sleep(interval_seconds)

    async def shutdown(self) -> None:
        for name, task in list(self._tasks.items()):
            if task is not None:
                task.cancel()
        self._tasks.clear()
