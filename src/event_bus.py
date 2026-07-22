import threading
from typing import Callable, Dict, List


class EventBus:
    """
    A lightweight, thread-safe PubSub Event Bus.
    Allows Decoupled components (e.g., STT, MediaPipe) to broadcast events
    to the UI/HUD without blocking their execution loops.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EventBus, cls).__new__(cls)
                cls._instance.subscribers: Dict[str, List[Callable]] = {}
        return cls._instance

    def subscribe(self, event_type: str, callback: Callable):
        with self._lock:
            if event_type not in self.subscribers:
                self.subscribers[event_type] = []
            self.subscribers[event_type].append(callback)

    def publish(self, event_type: str, data: any = None):
        with self._lock:
            if event_type in self.subscribers:
                # Execute callbacks in a new thread to avoid blocking the publisher
                for callback in self.subscribers[event_type]:
                    threading.Thread(target=callback, args=(data,), daemon=True).start()


# Global Singleton Event Bus
event_bus = EventBus()
