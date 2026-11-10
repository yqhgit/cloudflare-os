"""运营配置系统出站。只读 IT_OPS_BASE，不读取、不发送 Cookie 或 Authorization。"""

from __future__ import annotations

from typing import Any

from sdk.transport import request as _request

SYSTEM = "ops"
BASE_ENV = "IT_OPS_BASE"


def request(
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
    return _request(
        SYSTEM,
        BASE_ENV,
        method,
        path,
        operation=operation,
        query=query,
        json_body=json_body,
        files=files,
        form=form,
        headers=headers,
        path_params=path_params,
    )
