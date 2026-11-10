"""GENERATED from specs/config/*.yaml — do not edit. Re-run tools/gen_it_clients.py."""
from __future__ import annotations

from config._http import request

def uploadFile(*, file: str) -> dict:
    """写操作。
    批量改价证明材料上传

    返回 dict。字段未知，先用 preview 查看真实结构。
    """
    return request(
        "POST",
        "/evidenceFileService/uploadFile",
        operation="uploadFile",
        files={"file": file},
    )

