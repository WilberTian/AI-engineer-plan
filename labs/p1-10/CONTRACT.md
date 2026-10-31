# P1-10 接口约定

判分只看这一页。**这页没写的，都不判。**

约定里没有一个名字是我新造的——全部来自手册正文已有的代码（P1-5 的 `llm.py`、P1-9 的 `tools.py`、
P1-10 的 `loop.py`）。所以你按手册写完，就已经符合约定了，不需要为判分改结构。

---

## 1. 判分入口

| 项 | 约定 |
|---|---|
| 模块 | `agentlab.loop`（`src` 在 `PYTHONPATH` 里） |
| 函数 | `run(task, llm, registry, max_steps=…, timeout_s=…, max_result_chars=…)` |
| 位置参数 | 前三个按位置传：任务字符串、llm、registry |
| 关键字参数 | 判分会传 `max_steps` / `timeout_s` / `max_result_chars`，三个都必须**接受** |
| 返回 | 一个对象，至少有 `.status` / `.answer` / `.steps` / `.messages` / `.elapsed_ms` |

`max_steps` 语义：最多调用模型几次。`timeout_s`：总耗时上限（秒）。`max_result_chars`：单条工具结果进上下文前的截断长度。

```bash
# 判你自己的实现（默认在 ./src 下找 agentlab/）
python3 labs/p1-10/harness/run_checks.py

# 指定别的位置
python3 labs/p1-10/harness/run_checks.py --target /path/to/your/src
```

---

## 2. 返回值

| 字段 | 类型 | 约定 |
|---|---|---|
| `.status` | str | 只能是 `done` / `max_steps` / `timeout` / `error` 之一 |
| `.answer` | str | `done` 时是模型最后一条消息的正文；非 `done` 时可以是中止说明，也可以是空串 |
| `.steps` | list | 逐步记录；元素是什么结构**不判**，只要求可迭代、长度 ≥ 0 |
| `.messages` | list[dict] | 发出去的完整消息序列，判分**只读这个** |
| `.elapsed_ms` | float | 总耗时，毫秒 |

`status` 的取值集合判分只做「在里面」检查，不要求四种都实现到。
`.tool_calls`（站点版是个 property）视为可选派生属性，不判。

---

## 3. 消息协议（判分主要看这里）

这是 OpenAI 兼容协议，不是 Anthropic 的 block 结构。

| 角色 | 必须字段 |
|---|---|
| `system` | `role`, `content` |
| `user` | `role`, `content` |
| `assistant`（要调工具时） | `role`, `tool_calls`；`tool_calls[i]` 有 `id` / `function.name` / `function.arguments`（**字符串**，不是对象） |
| `assistant`（给结论） | `role`, `content` |
| `tool` | `role`, `tool_call_id`, `content` |

**唯一的硬不变量**：每一个出现在 `assistant.tool_calls` 里的 `id`，后面必须有一条 `role=="tool"`
且 `tool_call_id` 等于它的消息。少一条，下一轮请求就是 400。判分会逐个核对。

`arguments` 是**字符串**这一点尤其容易写错：它不是 dict。写成 dict 在本地看不出问题，
到真 API 上才炸。

---

## 4. 依赖的两个模块

判分要用你自己的 `tools.py` 造测试夹具，所以这三个名字必须存在且签名一致：

```python
ToolResult(ok: bool, content: str)
Tool(name: str, description: str, parameters: dict, fn: Callable[..., ToolResult])
Registry().register(tool)          # 还有 .specs() 和 .names()
```

`fn` 的调用方式是 `fn(**args)`，`args` 是从模型给的 JSON 字符串解析出来的 dict。

`llm` 这一侧判分不 import 你的 `LLM` 类，而是注入一个假 provider，它提供：

```python
llm.with_tools(messages, tools) -> 响应对象
响应对象.choices[0].message.{content, tool_calls}
message.model_dump(exclude_none=bool) -> dict     # 回填 assistant 消息用
```

也就是说：你的 loop 只要**不自己构造 SDK 对象**、只消费上面这几个属性，就能被判分。
站点版 `loop.py` 正是这么写的（L76-89）。

---

## 5. 明确不判的（你的自由）

| 不判 | 说明 |
|---|---|
| 内部结构、变量名、函数拆分 | 一层到底还是分层，随你 |
| 串行还是并发执行多个工具 | 只判「两个工具都真的被调用了」，不判快慢 |
| 错误文案的措辞 | 只判「是否回灌成一条 tool 消息」 |
| 用 dataclass 还是普通类 / dict | 只要字段取得到 |
| `Registry` 有没有公共 `get()` | 站点版直接摸 `_tools`（P1-9 没提供 `get`），这是实现细节 |
| `exclude_none` 用不用 | 只判 assistant 消息回填了 `tool_calls`；`content: null` 是否出现不判 |
| 状态里有没有 `error` | 只做「取值在集合内」检查 |
| 工具结果的截断后缀长什么样 | 只要有截断且提示了长度，或至少截断了 |

---

## 6. 判分覆盖了卡里 3 条验收的哪一条

卡上 `#p1-10` 的验收是三条，这里必须说清楚，别以为全绿就万事大吉：

| 卡里的验收 | 判分能覆盖吗 |
|---|---|
| ① 三个不同任务能选对工具 | **不能**。这需要真模型。判分注入的是脚本化的假 provider，它「选对」是因为脚本写死了 |
| ② `res.messages` 里能看到完整序列 | **能**，而且是重点（第 3 节） |
| ③ 不存在路径 → 模型靠同目录候选自我修正 | **一半**。工具层由 P1-9 保证（`read_file` 报错带候选），「模型因此改对」需要真模型 |

所以判分通过的意思是：**协议层对了**。它不能替你证明「模型用得对」——那部分只能真跑，
而且真跑的结果不可复现，不能当判据（只能当观察）。
