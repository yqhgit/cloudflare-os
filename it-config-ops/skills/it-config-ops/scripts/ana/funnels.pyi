from __future__ import annotations

def listFunnels(*, campaignId: str, page: int | None = None, pageSize: int | None = None) -> dict:
    """查询转化漏斗

    按活动查看漏斗，响应字段以运行结果为准

    分页参数: page, pageSize。

    返回 dict。字段未知，先用 preview 查看真实结构。
    """
    ...

def searchFunnels(*, keyword: str) -> list:
    """搜索漏斗

    只读搜索，不是写操作

    返回 list。字段: id: str。
    """
    ...

