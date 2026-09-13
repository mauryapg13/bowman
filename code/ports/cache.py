"""cache.py — content-addressed JSON cache for port calls (spec §8 P7).

Key = sha256 over the ordered parts + prompt_version. Files live under
code/cache/<key>.json and ship with the submission so the final run is
reproducible with zero network calls. Corrupt file == miss.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parents[1] / "cache"


def key(*parts: bytes | str, prompt_version: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        b = p if isinstance(p, bytes) else p.encode("utf-8")
        h.update(len(b).to_bytes(8, "big"))
        h.update(b)
    h.update(prompt_version.encode("utf-8"))
    return h.hexdigest()


class Cache:
    def __init__(self, directory: Path | str = DEFAULT_DIR):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    def get(self, k: str) -> dict | None:
        p = self.dir / f"{k}.json"
        if not p.is_file():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def put(self, k: str, value: dict) -> None:
        fd, tmp = tempfile.mkstemp(dir=self.dir, prefix=".tmp-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(value, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, self.dir / f"{k}.json")
