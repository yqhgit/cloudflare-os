from __future__ import annotations

def getCampaign(*, id: str) -> dict:
    """按 ID 查活动

    返回 dict。字段: id: str, name: str。
    """
    ...

def listCampaigns(*, page: int | None = None, pageSize: int | None = None, status: str | None = None) -> dict:
    """按页查询活动

    按状态过滤活动列表

    分页参数: page, pageSize。

    返回 dict。字段: total: int, list: list。
    """
    ...

