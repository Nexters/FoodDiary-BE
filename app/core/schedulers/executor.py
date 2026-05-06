import asyncio
from collections.abc import Callable
from contextlib import suppress

_registry: list[Callable[[], asyncio.Task]] = []


def scheduler(fn: Callable[[], asyncio.Task]) -> Callable[[], asyncio.Task]:
    _registry.append(fn)
    return fn


def start_all_schedulers() -> list[asyncio.Task]:
    return [fn() for fn in _registry]


async def stop_all_schedulers(tasks: list[asyncio.Task]) -> None:
    for task in tasks:
        task.cancel()
    for task in tasks:
        with suppress(asyncio.CancelledError):
            await task
