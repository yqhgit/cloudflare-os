"""GENERATED from schemas/*.yaml — do not edit. Re-run tools/gen_it_clients.py."""
from __future__ import annotations

from os import environ
from urllib.parse import quote

from _http import request
from typing import Any, Literal, NotRequired, TypedDict
from _gen_common import IpAddress, ServerRef

def _base() -> str:
    value = environ.get('IT_OPS_BI_BASE', '').rstrip('/')
    if not value:
        raise RuntimeError('IT_OPS_BI_BASE' + ' is not set')
    return value

class MetricPoint(TypedDict):
    ts: str
    value: float

class TimeSeries(TypedDict):
    server: ServerRef
    metric: NotRequired[str]
    points: list[MetricPoint]

class Alert(TypedDict):
    id: str
    server: ServerRef
    level: Literal['info', 'warn', 'critical']
    message: NotRequired[str]

def query_cpu(*, ip: IpAddress, start: str, end: str) -> TimeSeries:
    """查询机器 CPU 时序\n菜单: 指标"""
    path = '/api/metrics/cpu'
    return request('GET', _base() + path, query={"ip": ip, "start": start, "end": end}, json_body=None)

def list_alerts(*, ip: IpAddress | None = None, level: Literal['info', 'warn', 'critical'] | None = None) -> list[Alert]:
    """按机器列出未恢复告警\n菜单: 告警"""
    path = '/api/alerts'
    return request('GET', _base() + path, query={"ip": ip, "level": level}, json_body=None)

