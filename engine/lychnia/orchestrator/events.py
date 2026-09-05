"""In-memory event bus (spec §6.5). The API relays it over WebSocket; the CLI prints it."""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class Event:
    type: str
    payload: dict = field(default_factory=dict)
    t: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="milliseconds"))


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[queue.Queue[Event]] = []
        self._lock = threading.Lock()

    def subscribe(self) -> "queue.Queue[Event]":
        q: queue.Queue[Event] = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: "queue.Queue[Event]") -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def publish(self, type: str, **payload: object) -> Event:
        event = Event(type, dict(payload))
        with self._lock:
            subscribers = list(self._subscribers)
        for q in subscribers:
            q.put(event)
        return event
