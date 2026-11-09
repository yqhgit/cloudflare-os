"""GENERATED from schemas/*.yaml — do not edit. Re-run tools/gen_it_clients.py."""
from __future__ import annotations

from os import environ
from urllib.parse import quote

from _http import request
from typing import Any, Literal, NotRequired, TypedDict
from _gen_common import Idc, IpAddress, ServerRef

def _base() -> str:
    value = environ.get('IT_CMDB_BASE', '').rstrip('/')
    if not value:
        raise RuntimeError('IT_CMDB_BASE' + ' is not set')
    return value

class Nic(TypedDict):
    name: str
    addr: IpAddress
    role: NotRequired[Literal['business', 'management']]

class Server(TypedDict):
    identity: ServerRef
    idc: NotRequired[Idc]
    nics: NotRequired[list[Nic]]
    tags: NotRequired[list[str]]

class TagPatch(TypedDict):
    add: list[str]
    remove: NotRequired[list[str]]

def get_server(*, ip: IpAddress) -> Server:
    """按内网 IP 查询机器档案\n菜单: 机器管理"""
    path = '/api/servers/{ip}'
    path = path.replace('{ip}', quote(str(ip), safe=''))
    return request('GET', _base() + path, query=None, json_body=None)

def list_servers(*, idc: Idc | None = None) -> list[Server]:
    """按机房列出机器\n菜单: 机器管理"""
    path = '/api/servers'
    return request('GET', _base() + path, query={"idc": idc}, json_body=None)

def patch_server_tags(*, ip: IpAddress, body: TagPatch) -> Server:
    """写操作。\n为机器增减标签\n菜单: 标签"""
    path = '/api/servers/{ip}/tags'
    path = path.replace('{ip}', quote(str(ip), safe=''))
    return request('POST', _base() + path, query=None, json_body=body)

