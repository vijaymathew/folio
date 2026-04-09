from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[..., Any]]] = defaultdict(list)

    def subscribe(self, event_name: str, callback: Callable[..., Any]) -> None:
        self._listeners[event_name].append(callback)

    def emit(self, event_name: str, **payload: Any) -> None:
        for callback in self._listeners[event_name]:
            callback(**payload)
