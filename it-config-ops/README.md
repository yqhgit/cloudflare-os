# it-config-ops

运营配置（`ops`）和数据分析（`ana`）的参考实现。Skill 自带可 import 的脚本：OpenAPI 3 生成的客户端、按系统分开的传输层，以及 `find` / `preview` / `pages` / `emit`。不是 Cloudflare OS 内核的一部分，拷走 `skills/it-config-ops/` 即可。

认证不在客户端里。沙箱 `PYTHONPATH` 指向 `skills/it-config-ops/scripts`，并注入 `IT_OPS_BASE` 和 `IT_ANA_BASE`。各系统的 `_http.py` 只读自己的变量，不发送 cookie。菜单权限不预判，401/403 就是没有权限。

## 布局

```
skills/it-config-ops/SKILL.md
skills/it-config-ops/specs/<system>/*.yaml
skills/it-config-ops/scripts/ops/_http.py
skills/it-config-ops/scripts/ana/_http.py
skills/it-config-ops/scripts/<system>/<module>.py
skills/it-config-ops/scripts/sdk/
tools/gen_it_clients.py
```

## 命令

```bash
python3 tools/gen_it_clients.py
PYTHONPATH=skills/it-config-ops/scripts python3 -m unittest discover -s tests -v
```

接口变了只改 Skill 里的 YAML 再生成，不要把 host 或接口路径写进 `SKILL.md`。
