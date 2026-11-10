"""GENERATED from specs/ops/*.yaml — do not edit. Re-run tools/gen_it_clients.py."""
from __future__ import annotations

from ops._http import request

def getCampaign(*, id: str) -> dict:
    """按 ID 查活动

    返回 dict。字段: id: str, name: str。
    """
    return request(
        "GET",
        "/campaigns/{id}",
        operation="getCampaign",
        path_params={"id": id},
    )

def listCampaigns(*, page: int | None = None, pageSize: int | None = None, status: str | None = None) -> dict:
    """按页查询活动

    按状态过滤活动列表

    分页参数: page, pageSize。

    返回 dict。字段: total: int, list: list。
    """
    return request(
        "GET",
        "/campaigns",
        operation="listCampaigns",
        query={"page": page, "pageSize": pageSize, "status": status},
    )

