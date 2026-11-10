---
name: it-systems
description: 通过沙箱 Python 调用运营配置系统与数据分析系统。用户要查或改配置、活动、漏斗、证件附件，或要跨系统完成多步任务时使用。
---

# 运营配置与数据分析

可执行代码在本文件旁边的 `scripts/`。沙箱 `PYTHONPATH` 指向这个目录，然后 `from sdk import find`、`from config.<module> import ...`、`from analytics.<module> import ...`。不要把客户端抄进对话，也不要另写一套 HTTP。

认证由各系统网关注入。脚本不要处理 cookie。菜单权限因人而异，不要提前判断有没有某个菜单；接口返回 401/403 就是当前用户没有该菜单或接口权限。

`config` 是运营配置系统，只读环境变量 `IT_CONFIG_BASE`。`analytics` 是数据分析系统，只读环境变量 `IT_ANALYTICS_BASE`。一次任务写一段脚本，需要两边的数据就在这段脚本里 import 两个系统的函数。

## 何时使用

查询或变更运营配置、查看数据分析、一次任务跨多个业务域或两套系统。闲聊不用。

## 怎么执行

1. `from sdk import find`。用业务词搜索，例如 `find("config", "证件")` 或 `find("analytics", "漏斗")`。`find` 只返回 overlay 保留下来的接口；原始 YAML 里没被点名的接口没有函数。
2. 只 import 命中条目的 `module` 和 `id`。调用前可打开对应 `.pyi`，只使用其中存在的函数和参数名。
3. 命中条目 `fields_unknown` 为真时，先调用函数，再用 `preview` 看真实字段，然后在脚本里过滤。
4. 签名里的分页参数才是分页。用 `pages(fetch_page, start=1, size=20, max_pages=3)` 或自己循环，并在脚本里 `break`。不要指望客户端把所有页拉完。
5. 用 `emit` 交出最终结果。回答只引用 `emit` 打印出来的字段。

## 硬性约束

1. 只通过生成模块发请求。禁止 `urllib` / `requests` / `httpx` 访问未在模块中出现的 URL。
2. 禁止读取、设置、打印 Cookie、Authorization，以及 `os.environ` 里的密钥。
3. 只使用 `find` 结果或 `.pyi` 里存在的函数和参数名。
4. 空列表或 404：如实说明，禁止补全样本数据。
5. 403/401：告知当前用户没有权限，不要改凭证重试。
6. docstring 以「写操作」开头的函数：先 `emit` 将提交的参数（文件只给出路径和大小），等用户确认后再调用。

## 最小例子

```python
from sdk import emit, find, preview

hits = find("config", "证件")
emit(hits)
# 下一行换成 hits 里的 module 与 id，不要自己编函数名。
```

字段未知时，先取真实结构再过滤：

```python
from sdk import emit, preview

described = preview(payload)
emit(described)
```

不要在本文件中写 host、path 或 cookie。接口路径只以生成代码和 `find` 的结果为准。
