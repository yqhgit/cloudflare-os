"""GENERATED from schemas/*.yaml — do not edit. Re-run tools/gen_it_clients.py."""
from __future__ import annotations

from typing import Any

CATALOG: dict[str, Any] = {'cmdb': {'title': '配置管理',
          'domain': 'it',
          'module': 'cmdb',
          'base_env': 'IT_CMDB_BASE',
          'menus': {'servers': {'title': '机器管理',
                                'operations': [{'id': 'get_server',
                                                'mutation': False,
                                                'summary': '按内网 IP 查询机器档案'},
                                               {'id': 'list_servers',
                                                'mutation': False,
                                                'summary': '按机房列出机器'}]},
                    'tags': {'title': '标签',
                             'operations': [{'id': 'patch_server_tags',
                                             'mutation': True,
                                             'summary': '为机器增减标签'}]}}},
 'firewall': {'title': '防火墙',
              'domain': 'it',
              'module': 'firewall',
              'base_env': 'IT_FIREWALL_BASE',
              'menus': {'rules': {'title': '策略',
                                  'operations': [{'id': 'list_rules',
                                                  'mutation': False,
                                                  'summary': '按机器 IP 列出防火墙策略'},
                                                 {'id': 'update_rule',
                                                  'mutation': True,
                                                  'summary': '更新一条防火墙策略'}]}}},
 'ops_bi': {'title': '运营分析',
            'domain': 'ops',
            'module': 'ops_bi',
            'base_env': 'IT_OPS_BI_BASE',
            'menus': {'metrics': {'title': '指标',
                                  'operations': [{'id': 'query_cpu',
                                                  'mutation': False,
                                                  'summary': '查询机器 CPU 时序'}]},
                      'alerts': {'title': '告警',
                                 'operations': [{'id': 'list_alerts',
                                                 'mutation': False,
                                                 'summary': '按机器列出未恢复告警'}]}}}}

def systems_for_domain(domain: str) -> list[str]:
    return [name for name, spec in CATALOG.items() if spec["domain"] == domain]


def operations_for_menu(menu_title: str) -> list[dict[str, Any]]:
    """Resolve a user-facing menu name (or id) to operations across systems."""
    found: list[dict[str, Any]] = []
    needle = menu_title.strip()
    for system_id, spec in CATALOG.items():
        for menu_id, menu in spec["menus"].items():
            if needle in {menu_id, menu["title"], f"{spec['title']}/{menu['title']}"}:
                for operation in menu["operations"]:
                    found.append({
                        "system": system_id,
                        "module": spec["module"],
                        "domain": spec["domain"],
                        "menu": menu["title"],
                        **operation,
                    })
    return found
