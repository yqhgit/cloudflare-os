"""GENERATED from schemas/*.yaml — do not edit. Re-run tools/gen_it_clients.py."""
from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

IpAddress = str

Idc = Literal['n1', 'n2', 'n3']

class ServerRef(TypedDict):
    """机器身份，IT 与运营分析共用"""
    ip: IpAddress
    hostname: NotRequired[str]

class TimeRange(TypedDict):
    """闭区间时间窗"""
    start: str
    end: str

