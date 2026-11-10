"""Per-system HTTP. Callers pass their own base env name and never a credential."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

TIMEOUT_SECONDS = 30
_FORBIDDEN_HEADERS = {"cookie", "authorization", "proxy-authorization"}


def _drop_none(values: dict[str, Any] | None) -> dict[str, Any]:
    if not values:
        return {}
    return {key: value for key, value in values.items() if value is not None}


def _encode_multipart(
    files: dict[str, str], form: dict[str, Any],
) -> tuple[bytes, str]:
    boundary = "----it-config-ops-boundary"
    chunks: list[bytes] = []
    for name, value in form.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        chunks.append(str(value).encode())
        chunks.append(b"\r\n")
    for name, file_path in files.items():
        path = Path(file_path)
        data = path.read_bytes()
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(
            f'Content-Disposition: form-data; name="{name}"; filename="{path.name}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n".encode()
        )
        chunks.append(data)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def request(
    system: str,
    base_env: str,
    method: str,
    path: str,
    *,
    operation: str,
    query: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    files: dict[str, str] | None = None,
    form: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    path_params: dict[str, Any] | None = None,
) -> Any:
    base = os.environ.get(base_env, "").strip().rstrip("/")
    if not base:
        raise RuntimeError(f"{system} {operation} missing {base_env}")
    if path.startswith("http://") or path.startswith("https://"):
        raise RuntimeError(f"{system} {operation} refused absolute url")
    rendered = path
    for key, value in (path_params or {}).items():
        rendered = rendered.replace("{" + key + "}", urllib.parse.quote(str(value), safe=""))
    if "{" in rendered or "}" in rendered:
        raise RuntimeError(f"{system} {operation} unresolved path parameter")
    if not rendered.startswith("/"):
        rendered = "/" + rendered
    url = base + rendered
    if not (url == base or url.startswith(base + "/")):
        raise RuntimeError(f"{system} {operation} refused: url not under {base_env}")

    filtered_query = _drop_none(query)
    if filtered_query:
        url = url + "?" + urllib.parse.urlencode(filtered_query, doseq=True)

    safe_headers = {"Accept": "application/json"}
    for key, value in (headers or {}).items():
        if key.lower() in _FORBIDDEN_HEADERS:
            continue
        if value is None:
            continue
        safe_headers[key] = str(value)

    data: bytes | None = None
    if files or form:
        data, content_type = _encode_multipart(files or {}, _drop_none(form))
        safe_headers["Content-Type"] = content_type
    elif json_body is not None:
        data = json.dumps(_drop_none(json_body)).encode("utf-8")
        safe_headers["Content-Type"] = "application/json"

    outgoing = urllib.request.Request(url, data=data, method=method.upper(), headers=safe_headers)
    try:
        with urllib.request.urlopen(outgoing, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"{system} {operation} {err.code}: {body}") from err
    except json.JSONDecodeError as err:
        raise RuntimeError(f"{system} {operation} response is not json") from err
