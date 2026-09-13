"""Memory for the discovery loop.

A small persistent store of every candidate the engine has seen, keyed by the
object's identity. It gives the loop two things it needs to be a real search
rather than a one-shot: deduplication (never re-process or re-report the same
object) and accumulation across rounds. JSON on disk keeps it simple and
inspectable; swap for a database later without changing callers.
"""

from __future__ import annotations

import json
from pathlib import Path


class CandidateStore:
    def __init__(self) -> None:
        self._records: dict[str, dict] = {}

    def seen(self, key: str) -> bool:
        return key in self._records

    def add(self, key: str, record: dict) -> bool:
        """Store a record under key. Returns True if new, False if already seen."""
        if key in self._records:
            return False
        self._records[key] = record
        return True

    def all(self) -> list[dict]:
        return list(self._records.values())

    def __len__(self) -> int:
        return len(self._records)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self._records, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "CandidateStore":
        s = cls()
        p = Path(path)
        if p.exists():
            s._records = json.loads(p.read_text(encoding="utf-8"))
        return s
