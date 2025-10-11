from __future__ import annotations
from typing import List
from pathlib import Path
from ..domain.models import Alert


class ConsoleNotifier:
    def notify(self, alerts: List[Alert]) -> None:
        for a in alerts:
            print(f"[{a.level.upper()}] {a.message}")


class FileNotifier:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def notify(self, alerts: List[Alert]) -> None:
        with self._path.open("a", encoding="utf-8") as f:
            for a in alerts:
                f.write(f"[{a.level.upper()}] {a.message}\n")
