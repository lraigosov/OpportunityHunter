from __future__ import annotations
import json
from typing import Dict, Any
from pathlib import Path

class JsonConfigLoader:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def get(self) -> Dict[str, Any]:
        with self._path.open("r", encoding="utf-8") as f:
            return json.load(f)
