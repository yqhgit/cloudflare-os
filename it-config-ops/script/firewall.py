"""GENERATED from schemas/*.yaml — do not edit. Re-run tools/gen_it_clients.py."""
from __future__ import annotations

from os import environ
from urllib.parse import quote

from _http import request
from typing import Any, Literal, NotRequired, TypedDict
from _gen_common import IpAddress, ServerRef

def _base() -> str:
    value = environ.get('IT_FIREWALL_BASE', '').rstrip('/')
    if not value:
        raise RuntimeError('IT_FIREWALL_BASE' + ' is not set')
    return value

class FirewallRule(TypedDict):
    id: str
    device: ServerRef
    action: Literal['allow', 'deny']
    port: NotRequired[int]
    comment: NotRequired[str]

class FirewallRuleUpdate(TypedDict):
    id: str
    device: ServerRef
    action: Literal['allow', 'deny']
    port: NotRequired[int]
    comment: NotRequired[str]
    change_ticket: NotRequired[str]

def list_rules(*, device_ip: IpAddress) -> list[FirewallRule]:
    """按机器 IP 列出防火墙策略\n菜单: 策略"""
    path = '/api/rules'
    return request('GET', _base() + path, query={"device_ip": device_ip}, json_body=None)

def update_rule(*, id: str, body: FirewallRuleUpdate) -> FirewallRule:
    """写操作。\n更新一条防火墙策略\n菜单: 策略"""
    path = '/api/rules/{id}'
    path = path.replace('{id}', quote(str(id), safe=''))
    return request('PUT', _base() + path, query=None, json_body=body)

