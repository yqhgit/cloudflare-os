# it-systems

运营配置（`config`）和数据分析（`analytics`）的参考实现。Skill 名是 `it-systems`。自带可 import 的脚本：OpenAPI 3 生成的客户端、按系统分开的传输层，以及 `find` / `preview` / `pages` / `emit`。不是 Cloudflare OS 内核的一部分，拷走 `skills/it-systems/` 即可。

认证不在客户端里。沙箱 `PYTHONPATH` 指向 `skills/it-systems/scripts`，并注入 `IT_CONFIG_BASE` 和 `IT_ANALYTICS_BASE`。各系统的 `_http.py` 只读自己的变量，不发送 cookie。菜单权限不预判，401/403 就是没有权限。

## 布局

```
skills/it-systems/SKILL.md
skills/it-systems/specs/config/*.yaml
skills/it-systems/specs/analytics/*.yaml
skills/it-systems/scripts/config/_http.py
skills/it-systems/scripts/analytics/_http.py
skills/it-systems/scripts/<system>/<module>.py
skills/it-systems/scripts/sdk/
tools/gen_it_clients.py
```

`gen_report.txt` 在 Skill 目录下，记录生成时跳过的接口，不放进 `scripts/`。

## 命令

```bash
python3 tools/gen_it_clients.py
PYTHONPATH=skills/it-systems/scripts python3 -m unittest discover -s tests -v
```

接口变了只改 Skill 里的 YAML 再生成，不要把 host 或接口路径写进 `SKILL.md`。
