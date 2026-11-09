"""唯一出站入口。鉴权由 iptables 注入 cookie，这里不读、不设、不打印凭证。"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

TIMEOUT_SECONDS = 30


def allowed_bases() -> list[str]:
    bases: list[str] = []
    for key, value in os.environ.items():
        if key.startswith("IT_") and key.endswith("_BASE") and value.strip():
            bases.append(value.strip().rstrip("/"))
    return bases


def _assert_allowed(url: str) -> None:
    bases = allowed_bases()
    if not bases:
        raise PermissionError("no IT_*_BASE environment variables configured")
    if not any(url == base or url.startswith(base + "/") for base in bases):
        raise PermissionError(f"url not in allowlist: {url}")


def request(
    method: str,
    url: str,
    *,
    query: dict[str, Any] | None = None,
    json_body: Any | None = None,
) -> Any:
    if query:
        filtered = {key: value for key, value in query.items() if value is not None}
        if filtered:
            url = url + "?" + urllib.parse.urlencode(filtered, doseq=True)
    _assert_allowed(url)

    data = None
    headers = {"Accept": "application/json"}
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, method=method.upper(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"{method.upper()} {url} {err.code}: {body}") from err
