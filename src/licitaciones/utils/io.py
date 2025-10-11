from __future__ import annotations
from typing import Iterable
from pathlib import Path
import orjson


def write_ndjson(path: str | Path, items: Iterable[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        for item in items:
            f.write(orjson.dumps(item))
            f.write(b"\n")
