import time
import asyncio
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class LogEntry:
    timestamp: str
    action: str
    detail: str
    records: int = 0
    size_bytes: int = 0
    status: int = 200
    duration_ms: int = 0


class AppState:
    def __init__(self):
        self.start_time = time.time()
        self.mode: str = "IDLE"
        self.progress_current: int = 0
        self.progress_total: int = 0
        self.current_item: str = ""
        self.eta_seconds: int = 0
        self.last_activity: str | None = None
        self.records_processed: int = 0
        self.errors_total: int = 0
        self.last_error: str | None = None
        self.logs: deque[LogEntry] = deque(maxlen=10000)
        self.active_job_id: str | None = None
        self._subscribers: list[asyncio.Queue] = []

    @property
    def uptime_seconds(self) -> int:
        return int(time.time() - self.start_time)

    @property
    def status(self) -> str:
        if self.mode == "ERROR":
            return "error"
        if self.errors_total > 0 and self.error_rate > 0.05:
            return "degraded"
        return "healthy"

    @property
    def error_rate(self) -> float:
        if self.records_processed == 0:
            return 0.0
        return self.errors_total / self.records_processed

    @property
    def progress_percentage(self) -> float:
        if self.progress_total == 0:
            return 0.0
        return round(self.progress_current / self.progress_total * 100, 1)

    def add_log(self, entry: LogEntry):
        self.logs.append(entry)
        self.last_activity = entry.timestamp
        self._notify_subscribers("log", {
            "timestamp": entry.timestamp,
            "action": entry.action,
            "detail": entry.detail,
            "records": entry.records,
            "size_bytes": entry.size_bytes,
            "status": entry.status,
            "duration_ms": entry.duration_ms,
        })

    def new_job_id(self) -> str:
        self.active_job_id = str(uuid.uuid4())[:8]
        return self.active_job_id

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)

    def _notify_subscribers(self, event_type: str, data: dict):
        for q in self._subscribers:
            try:
                q.put_nowait({"event": event_type, "data": data})
            except asyncio.QueueFull:
                pass

    def notify_status(self):
        self._notify_subscribers("status", {
            "mode": self.mode,
            "progress": self.progress_percentage,
            "current_item": self.current_item,
        })

    def notify_error(self, message: str):
        self._notify_subscribers("error", {
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def notify_health(self):
        self._notify_subscribers("health", {
            "status": self.status,
            "uptime_seconds": self.uptime_seconds,
        })


state = AppState()
