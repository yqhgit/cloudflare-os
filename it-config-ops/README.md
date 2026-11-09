# it-config-ops

内网「对话执行配置 / 运营分析」的参考实现：YAML（含 `$ref`）机械生成 Python 客户端，Skill 只做目录与禁令。不是 Cloudflare OS 内核的一部分，可整目录拷到内网。

## 设计

- **系统** `domain: it | ops`：配置管理、防火墙、运营分析。
- **菜单**：机器管理、标签、策略、指标、告警。用户口中的菜单名用 `catalog.operations_for_menu()` 解析到模块。
- **跨系统**：一次任务一个脚本，多模块 import；共享类型在 `schemas/common.yaml`（`ServerRef`），用 `$ref` 引用，禁止把中间结果经模型抄写后再调下一个系统。
- **`$ref`**：文件内 `#/components/schemas/Nic`、跨文件 `common.yaml#/schemas/ServerRef`、嵌套 ref、`allOf` 合并（见防火墙 `FirewallRuleUpdate`）。

认证不在客户端里。沙箱只注入 `IT_CMDB_BASE`、`IT_FIREWALL_BASE`、`IT_OPS_BI_BASE`。cookie 由 iptables 注入。`script/_http.py` 拒绝非这些前缀的 URL。

## 布局

```
schemas/           YAML 真相（含 $ref）
tools/gen_it_clients.py
script/_http.py    手写运行时，生成器不会覆盖
script/_gen_common.py, cmdb.py, firewall.py, ops_bi.py, catalog.py
skills/it-config-ops/SKILL.md
examples/cross_system_task.py
tests/
```

## 命令

```bash
python3 tools/gen_it_clients.py
PYTHONPATH=script python3 -m unittest discover -s tests -v
```

## 给对话智能体

把 `skills/it-config-ops/SKILL.md` 配成 Skill；沙箱 `PYTHONPATH` 指向 `script/`。接口变了只改 YAML 再生成，不要改 Skill 里的 path。
