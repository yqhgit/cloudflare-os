"""跨系统任务示例：CMDB 身份 → 运营分析指标 → 防火墙策略。

同一脚本内用变量传递 ServerRef.ip，不把中间结果送回模型再抄写。
运行前设置 IT_CMDB_BASE / IT_FIREWALL_BASE / IT_OPS_BI_BASE。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "script"))

from catalog import operations_for_menu  # noqa: E402
from cmdb import get_server  # noqa: E402
from firewall import list_rules  # noqa: E402
from ops_bi import list_alerts, query_cpu  # noqa: E402


def diagnose(ip: str, start: str, end: str) -> dict[str, object]:
    # 菜单「机器管理」属于 IT/cmdb；「指标」「告警」属于运营分析；「策略」属于防火墙。
    assert operations_for_menu("机器管理")
    server = get_server(ip=ip)
    identity = server["identity"]
    bound_ip = identity["ip"]
    return {
        "server": identity,
        "idc": server.get("idc"),
        "cpu": query_cpu(ip=bound_ip, start=start, end=end),
        "alerts": list_alerts(ip=bound_ip),
        "firewall_rules": list_rules(device_ip=bound_ip),
    }


if __name__ == "__main__":
    result = diagnose("10.0.0.1", "2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z")
    print(json.dumps(result, ensure_ascii=False, indent=2))
