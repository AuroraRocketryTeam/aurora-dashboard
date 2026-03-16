"""
In-memory buffer + persistence.

During a live session (SERIAL / LORA source) every TelemetryFrame is appended
to a deque limited at maxlen. When save() is called
maybe from the dashboard), the buffer is serialised to CSV or JSON.
"""

import csv
import json
import logging
import os
import time
from collections import deque
from datetime import datetime
from typing import Optional

from models.telemetry import TelemetryFrame

log = logging.getLogger(__name__)

class Recorder:
    def __init__(self, maxlen: int = 100_000, enabled: bool = True, autosave_every: int = 0):
        self._buf: deque[TelemetryFrame] = deque(maxlen=maxlen)
        self.enabled = enabled
        self._recording_since: Optional[float] = None
        self._autosave_every = autosave_every
        # Each autosave overwrites the same file
        self._autosave_path: Optional[str] = None

    def record(self, frame: TelemetryFrame) -> None:
        if not self.enabled:
            return
        if self._recording_since is None:
            self._recording_since = time.time()
            if self._autosave_every > 0:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                self._autosave_path = os.path.join("autosave", f"autosave_{ts}.csv")
                log.info("Recorder: autosave enabled: interval %d frames in %s",
                         self._autosave_every, self._autosave_path)
        self._buf.append(frame)
        if self._autosave_every > 0 and len(self._buf) % self._autosave_every == 0:
            try:
                self._save_csv(self._autosave_path)
                log.debug("Recorder: autosaved %d frames to %s",
                          len(self._buf), self._autosave_path)
            except Exception as e:
                log.error("Recorder: autosave failed: %s", e)

    # *** Queries from the dash ***

    @property
    def count(self) -> int:
        return len(self._buf)

    @property
    def recording_duration(self) -> float:
        """Seconds since the first frame was received."""
        if self._recording_since is None:
            return 0.0
        return time.time() - self._recording_since

    def status(self) -> dict:
        return {
            "frames": self.count,
            "duration_s": round(self.recording_duration, 1),
            "enabled": self.enabled,
            "autosave_every": self._autosave_every,
            "autosave_path": self._autosave_path,
        }

    # *** Persistence ***

    def save(self, path: Optional[str] = None, fmt: str = "csv") -> str:
        """
        Args:
            path: Target file path. By default auto-generates a timestamped file
                  in the current directory (e.g. flight_20240312_143022.csv).
            fmt:  "csv" or "json".

        Returns:
            The path that was written.
        """
        if not self._buf:
            raise ValueError("Buffer is empty.")

        if path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = f"flight_{ts}.{fmt}"

        if fmt == "csv":
            self._save_csv(path)
        elif fmt == "json":
            self._save_json(path)
        else:
            raise ValueError(f"Unknown format: {fmt!r}. Use 'csv' or 'json'.")

        log.info("Recorder: saved %d frames to %s", len(self._buf), path)
        return path

    def _save_csv(self, path: str) -> None:
        rows = [f.to_csv_row() for f in self._buf]
        if not rows:
            return
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        fieldnames = list(rows[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _save_json(self, path: str) -> None:
        data = [f.to_dashboard_json() for f in self._buf]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    # *** control ***

    def clear(self) -> None:
        self._buf.clear()
        self._recording_since = None
        log.info("Recorder: buffer cleared")

    def start(self) -> None:
        self.enabled = True

    def stop(self) -> None:
        self.enabled = False
