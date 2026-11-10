"""GENERATED from specs/config/*.yaml — do not edit. Re-run tools/gen_it_clients.py."""
from __future__ import annotations

from config._http import request

def createLabel(*, name: str, note: str | None = None) -> dict:
    """写操作。
    创建标签

    返回 dict。字段: id: str。
    """
    return request(
        "POST",
        "/labels",
        operation="createLabel",
        json_body={"name": name, "note": note},
    )

