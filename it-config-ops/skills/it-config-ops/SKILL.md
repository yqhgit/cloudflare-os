---
name: it-config-ops
description: 通过沙箱 Python 调用内网 IT 配置与运营分析系统（CMDB、防火墙、指标、告警）。用户询问机器、配置、变更、防火墙策略、CPU/告警或要跨系统排查时使用。
---

# 内网 IT 配置与运营分析

用 `script/` 下生成模块发请求。认证由平台 iptables 注入 cookie，脚本不要处理凭证。

跨系统时：**一个脚本 import 多个模块**，用变量传递 `ServerRef.ip` 等共享字段，不要把中间 JSON 用自然语言转述后再调下一个系统。

## 何时使用

查机器/配置、改防火墙、看 CPU 或告警、跨 IT 与运营分析排查。闲聊不用。

## 怎么执行

1. 若用户说的是菜单名（机器管理、策略、指标、告警），先 `from catalog import operations_for_menu` 看属于哪个 `module`。
2. 打开 `script/<module>.py`（或同名类型），只使用其中存在的函数和参数。
3. 写一段 Python，`print(json.dumps(结果, ensure_ascii=False, indent=2))`。
4. 回答只引用这段输出。禁止心算或补全。

## 系统与菜单

| domain | module | 系统 | 菜单 |
|---|---|---|---|
| it | `cmdb` | 配置管理 | 机器管理、标签 |
| it | `firewall` | 防火墙 | 策略 |
| ops | `ops_bi` | 运营分析 | 指标、告警 |

IT 与运营分析共用 `ServerRef`（`ip` / `hostname`）。从 CMDB 拿到 `identity` 后，把 `ip` 传给防火墙和运营分析。

## 硬性约束

1. 只通过 `script/` 生成模块发请求（`from cmdb import get_server`）。
2. 禁止 `urllib` / `requests` / `httpx` 访问未在模块中出现的 URL。
3. 禁止读取、设置、打印 Cookie、Authorization、以及 `os.environ` 里的密钥。环境变量只应有 `IT_*_BASE`。
4. 调用前打开对应模块，只使用文件里存在的函数和参数名。
5. 最终结果必须 `json.dumps(..., ensure_ascii=False, indent=2)` 打印。
6. 空列表或 404：如实说明，禁止补全样本数据。
7. 403/401：当前用户没有权限，不要改凭证重试。
8. docstring 含「写操作」的函数：先列出将提交的参数，等用户确认后再调用。

## 跨系统最小例子

```python
import json
from cmdb import get_server
from firewall import list_rules
from ops_bi import query_cpu, list_alerts

server = get_server(ip="10.0.0.1")
ip = server["identity"]["ip"]
result = {
    "server": server["identity"],
    "cpu": query_cpu(ip=ip, start="2026-01-01T00:00:00Z", end="2026-01-01T01:00:00Z"),
    "alerts": list_alerts(ip=ip),
    "rules": list_rules(device_ip=ip),
}
print(json.dumps(result, ensure_ascii=False, indent=2))
```

不要在本文件中写 host、path 或 cookie。路径只以生成代码为准。
