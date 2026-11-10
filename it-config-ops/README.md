# it-config-ops

运营配置（`ops`）和数据分析（`ana`）的参考实现。OpenAPI 3 机械生成 Python 客户端，Skill 只说明怎么发现接口和怎么约束脚本。不是 Cloudflare OS 内核的一部分，可整目录拷到内网。

认证不在客户端里。沙箱注入 `IT_OPS_BASE` 和 `IT_ANA_BASE`。各系统的 `script/<system>/_http.py` 只读自己的变量，不发送 cookie。菜单权限不预判，401/403 就是没有权限。

## 布局

```
specs/ops/*.yaml          OpenAPI 3，servers.url 不作为请求地址
specs/ana/*.yaml
tools/gen_it_clients.py   确定性生成，不调用 LLM
script/ops/_http.py       手写，生成器不覆盖
script/ana/_http.py
script/ops/<module>.py    生成的函数，按 path 第一段分文件
script/sdk/find.py        在本地 spec 里搜索
script/sdk/preview.py     preview 与 emit
script/sdk/pages.py       显式分页
skills/it-config-ops/SKILL.md
```

## 命令

```bash
python3 tools/gen_it_clients.py
PYTHONPATH=script python3 -m unittest discover -s tests -v
```

沙箱 `PYTHONPATH` 指向 `script/`。接口变了只改 YAML 再生成，不要把 path 写进 Skill。
