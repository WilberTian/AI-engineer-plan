# P1-9 接口约定（判分只看这一页）

被判对象：`src/agentlab/tools.py`（你的实现）。
判分器：`harness/run_checks.py`，14 条，无第三方依赖。

```bash
python3 labs/p1-9/harness/run_checks.py --target ~/code/agentlab/src
```

---

## 1. `agentlab.tools` 必须提供这些名字

手册 p1-9 已经写了它们的形状，这里只是把「哪些算公共面」定下来：

| 名字 | 要求 |
|---|---|
| `ToolResult(ok, content)` | dataclass，至少这两个字段；`meta` 可选 |
| `Tool(name, description, parameters, fn)` | dataclass，四个字段都要 |
| `Registry()` | 有 `register(tool)`、`specs()`、`names()` |
| `build_registry() -> Registry` | 注册三个工具 |
| `read_file` / `search_notes` / `fetch_url` | **模块级函数**，可直接调用 |

最后一行是关键：判分直接调 `tools.read_file(path=...)`，不经过 Registry。
这样判分不依赖你把工具函数存在哪、叫什么内部键名。

## 2. Registry 的三条行为

- `register` 遇到重名**必须当场抛异常**。静默覆盖后的表现是「模型总是调错工具」，比崩溃难查十倍
- `specs()` 返回 OpenAI 兼容形状：`{"type": "function", "function": {name, description, parameters}}`
- `names()` 返回已注册的名字

## 3. 三个工具的边界

| 工具 | 约定 |
|---|---|
| `read_file(path)` | 只接受相对路径；拒绝绝对路径；拒绝含 `..` 的路径 |
| `read_file` 报错 | `content` 里**必须带同目录候选文件名**（这是卡里验收的原文） |
| `search_notes(query)` | 没搜到是 `ok=True` + 说明，不算错误 |
| `fetch_url(url)` | 只接受 `http/https`，且在**调用 http 库之前**拒绝 |
| 任何工具 | 都不许抛异常。错误一律变成 `ToolResult(ok=False, content=...)` |

## 4. 路径与目录

工具用 **CWD** 解析相对路径。判分会 chdir 到一个临时目录，并在里面同时备好：

```
data/notes/{todo,loop,deep/nested}.md
notes/{todo,loop,deep/nested}.md
```

两处都给，是因为手册里 `NOTES_DIR` 写的是 `data/notes`，而 `read_file` 的例子写的是 `notes/todo.md`——
判错一个目录名没有教学价值。**但你自己的项目里应该只留一种。**

## 5. 判不了的部分

- **`fetch_url` 真联网抓取**：要外网，且被判环境不一定装了 `httpx`。判分只验证「协议闸」和「不抛异常」
- **模型会不会选对工具**：那是 p1-10 的事，而且要真模型

全绿的含义是：工具层的边界和报错信息对了。工具「好用不好用」（description 写得准不准）只能靠 p1-11 的三组对照实验。
