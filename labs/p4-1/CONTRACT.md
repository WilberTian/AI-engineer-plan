# P4-1 接口约定：故障注入框架

判分器只看这一页。你按手册写完就自动符合，不用为了判分改结构。

## §1 落点与公共名

```
agentlab/resilience/faults.py
    SPEC                       FaultSpec 实例，模块导入时从 FAULTS 环境变量固化
    SPEC.enabled               bool
    SPEC.slow / timeout / dirty / exception / empty   float，0–1
    maybe_fault(name: str, result: ToolResult) -> ToolResult

agentlab/tools.py
    ToolResult(ok: bool, content: str)      dataclass，P1 就有
```

`FAULTS` 环境变量格式：`slow=0.3,dirty=0.2`。

## §2 判什么（13 条）

| # | 断言 | 为什么它值得判 |
|---|---|---|
| 1 | FAULTS 为空时返回**同一个对象**（`is`，不是 `==`） | 「完全没影响」不是「差不多没影响」 |
| 2 | 空配置与全 0 配置都算关闭 | `slow=0` 不该被当成开启 |
| 3 | 未知键被忽略，加载不崩 | 环境变量是手敲的 |
| 4 | 未知键与已知键混写时，已知的仍生效 | 别因为一个错字把整串配置吃掉 |
| 5 | `exception=1.0` 抛异常，消息含工具名 | 不带工具名的日志等于没日志 |
| 6 | `timeout=1.0` 返回 `ok=False`，消息含工具名 | 同上 |
| 7 | `dirty=1.0` 返回 `ok=True` 且内容是**合法但不同**的 JSON | 标成 `ok=False` 就退化成超时那类，测不出「把 null 当答案」 |
| 8 | `empty=1.0` 返回空串 | 工具成功但没找到，是最常见的一类 |
| 9 | `slow=1.0` 真调用 sleep，且**仍返回正确结果** | 变慢不是变错。返回错误就变成了超时那类 |
| 10 | 三种「返回结果」的故障都返回 `ToolResult` | 混进裸字符串，下游 `result.ok` 当场 AttributeError |
| 11 | 同一配置加载两次，故障序列一致 | 不可复现的故障没法排查，也没法写回归 |
| 12 | 多故障同开 1.0 时走哪条是**固定顺序**，不是随机分派 | 决定了「总故障率 ≈ 相加」这个估算成不成立 |
| 13 | `slow=abc` 这类非法值当场报错 | 静默当成关闭是最坏的：你以为在测故障，其实在跑正常模式 |

第 11 条容易写错：比较 `ok` 没用，因为 `dirty` 是 `ok=True`、正常结果也是 `ok=True`。比内容。

## §3 不判什么

- **「在 loop 里接入」**：`result = maybe_fault(name, result)` 这一行要真跑一次 eval 才知道有没有漏掉某个工具调用点。离线只能判注入器本身。
- **「FAULTS 为空时通过率一致」**：需要真模型跑两遍 eval。
- **故障率是否符合统计预期**：手册明说「五种各抽一次随机数，不是抽一次再分派，所以总故障率近似相加」，第 12 条只判顺序固定，不判分布。

## §4 你的自由（判分不碰）

- `FaultSpec` 加字段、改名、换成 `TypedDict`
- 用装饰器 `@inject_faults` 包住工具注册表，而不是在 loop 里逐点调用
- 种子取 42 / 0 / 从环境变量读（只要同配置两次一致）
- `maybe_fault` 增加 `target=tool_name` 定向注入（手册卡住怎么办里提到的那种）

## §5 怎么跑

```bash
python3 labs/p4-1/harness/run_checks.py --target ~/code/agentlab-project
python3 labs/p4-1/harness/run_checks.py --target . --filter dirty     # 只跑一条
```

退出码 0 = 全过，1 = 有红，2 = 找不到被判对象。

维护者用 `tools/verify_reference.py`（从 `stage-p4.html` 现抽参考实现）和 `tools/self_test.py`（塞 7 个 bug 反向验证）。

## §6 边界

判分器**不联网、不花额度、不装依赖**。全绿说明注入器本身的五类故障开关都对了。

它不说明你的 agent 在故障下「不崩 + 可读」——那是 P4-2 的 guards 该管的。
