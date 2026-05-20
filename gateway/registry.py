import json
import threading
import time
from dataclasses import dataclass, asdict, field
from typing import Optional


@dataclass
class ToolRecord:
    name: str
    route: str
    port: int
    status: str  # starting | running | stopped | crashed
    pid: Optional[int] = None
    started_at: float = field(default_factory=time.time)
    manifest: dict = field(default_factory=dict)


class Registry:
    def __init__(self):
        self._tools: dict[str, ToolRecord] = {}
        self._lock = threading.Lock()

    def register(self, record: ToolRecord):
        with self._lock:
            self._tools[record.name] = record

    def unregister(self, name: str):
        with self._lock:
            self._tools.pop(name, None)

    def get(self, name: str) -> Optional[ToolRecord]:
        with self._lock:
            return self._tools.get(name)

    def get_by_route(self, route: str) -> Optional[ToolRecord]:
        with self._lock:
            for t in self._tools.values():
                if t.route == route:
                    return t
        return None

    def list_all(self) -> list[ToolRecord]:
        with self._lock:
            return list(self._tools.values())

    def save_to_disk(self, path: str):
        with self._lock:
            data = {name: asdict(r) for name, r in self._tools.items()}
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load_from_disk(self, path: str):
        try:
            with open(path) as f:
                data = json.load(f)
        except FileNotFoundError:
            return
        with self._lock:
            for name, d in data.items():
                self._tools[name] = ToolRecord(**d)
