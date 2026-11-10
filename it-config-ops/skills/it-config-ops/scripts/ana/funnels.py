"""GENERATED from specs/ana/*.yaml — do not edit. Re-run tools/gen_it_clients.py."""
from __future__ import annotations

from ana._http import request

def listFunnels(*, campaignId: str, page: int | None = None, pageSize: int | None = None) -> dict:
    """查询转化漏斗

    按活动查看漏斗，响应字段以运行结果为准

    分页参数: page, pageSize。

    返回 dict。字段未知，先用 preview 查看真实结构。
    """
    return request(
        "GET",
        "/funnels",
        operation="listFunnels",
        query={"campaignId": campaignId, "page": page, "pageSize": pageSize},
    )

def searchFunnels(*, keyword: str) -> list:
    """搜索漏斗

    只读搜索，不是写操作

    返回 list。字段: id: str。
    """
    return request(
        "POST",
        "/funnels/search",
        operation="searchFunnels",
        json_body={"keyword": keyword},
    )

