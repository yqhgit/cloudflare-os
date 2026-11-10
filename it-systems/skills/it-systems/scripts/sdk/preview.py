"""Look at a real JSON value, and print a bounded copy of a final result."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

# Cloudflare Code Mode clips a tool result at about 6000 tokens. 4 characters
# is a rough token. The full value stays in the process; only the print is clipped.
TOKEN_LIMIT = 6000
CHARS_PER_TOKEN = 4
TRUNCATION_MARK = "--- TRUNCATED ---"
_STRING_LIMIT = 80


def _short(value: Any, n: int) -> Any:
    if isinstance(value, str):
        return value if len(value) <= _STRING_LIMIT else value[:_STRING_LIMIT] + "..."
    if isinstance(value, dict):
        return {key: _short(item, n) for key, item in list(value.items())[:n]}
    if isinstance(value, list):
        return [_short(item, n) for item in value[:n]]
    return value


def preview(value: Any, n: int = 5) -> dict[str, Any]:
    """Structural sample of a response. Not an HTTP HEAD request."""
    if n < 1:
        raise ValueError("n must be at least 1")
    described: dict[str, Any] = {"type": type(value).__name__}
    if isinstance(value, dict):
        described["keys"] = list(value.keys())
        described["sample"] = _short(value, n)
    elif isinstance(value, list):
        described["array_len"] = len(value)
        described["sample"] = _short(value, n)
        if value and isinstance(value[0], dict):
            described["keys"] = list(value[0].keys())
    else:
        described["sample"] = _short(value, n)
    return described


def emit(value: Any) -> None:
    """Print JSON. Over the token budget, print a prefix plus a marker and write the full file."""
    text = json.dumps(value, ensure_ascii=False, indent=2)
    limit = TOKEN_LIMIT * CHARS_PER_TOKEN
    if len(text) <= limit:
        print(text)
        return
    directory = Path(os.environ.get("IT_SESSION_DIR", ".it-session"))
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    path = directory / f"emit-{digest}.json"
    path.write_text(text, encoding="utf-8")
    print(text[:limit])
    print(TRUNCATION_MARK)
    print(f"full: {path}")
