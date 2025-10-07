"""Simple in-process event broadcaster for Server-Sent Events (SSE)."""

import threading
import queue
import json
from typing import Dict, Any


class EventStream:
    """Thread-safe pub/sub queue for pushing backend events to SSE clients."""

    def __init__(self, max_queue_size: int = 100):
        self._subscribers: set[queue.Queue] = set()
        self._lock = threading.Lock()
        self._max_queue_size = max_queue_size

    def subscribe(self) -> queue.Queue:
        """Register a new subscriber and return its queue."""
        q = queue.Queue(maxsize=self._max_queue_size)
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, subscriber: queue.Queue) -> None:
        """Remove a subscriber queue (safe to call multiple times)."""
        with self._lock:
            self._subscribers.discard(subscriber)

    def publish(self, event: Dict[str, Any]) -> None:
        """Push an event to all subscribers without blocking."""
        if not event:
            return

        # Create a JSON payload once to reuse across subscribers
        payload = json.dumps(event, ensure_ascii=False)

        with self._lock:
            subscribers = list(self._subscribers)

        for subscriber in subscribers:
            try:
                subscriber.put_nowait(payload)
            except queue.Full:
                # Drop the oldest event if queue is full to avoid blocking
                try:
                    subscriber.get_nowait()
                except queue.Empty:
                    pass
                try:
                    subscriber.put_nowait(payload)
                except queue.Full:
                    # If it is still full, skip this subscriber
                    continue


# Global event stream instance for device-related notifications
device_event_stream = EventStream()

