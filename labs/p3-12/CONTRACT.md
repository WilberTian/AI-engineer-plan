# P3-12 接口约定：上下文的三条线索

判分器只看这一页。

## §1 落点与公共名

```
agentlab/context.py
    STATE_BAR: str                                   状态栏模板（固定字段）
    assemble(system, history, state_bar, user_text) -> list[dict]
    cached_ratio(usage) -> float
```

`assemble` 返回消息列表，每条含 `role` 与 `content`。
`cached_ratio` 算缓存命中率，读 OpenAI 风格的 `prompt_tokens_details.cached_tokens`。

## §2 判什么（15 条）

| 组 | # | 断言 |
|---|---|---|
| 组装 | 1–3 | 第一条是 `system` 且内容等于入参；`history` 原样追加、**顺序不变**；最后一条是 `user` |
| 状态栏 | 4–5 | `state_bar` 在**最后一条 user** 的内容里；`state_bar` 不出现在 `system` 里 |
| 前缀稳定 | 6 | **换 `state_bar`，前 N 条一字不改**（这是本卡的硬约束） |
| 纯函数 | 7–8 | 传进来的 `history` 列表没被改；返回的是新列表 |
| 边界 | 9–10 | 空 `history` → 只有 2 条消息；每条消息都有 `role` 与 `content`，`role` 合法 |
| 命中率 | 11–14 | hit=50/total=200 → 0.25；没有缓存字段 → 0；`total=0` → 0（不除零）；`usage=None` → 0 |
| 状态栏 | 15 | `STATE_BAR` 含「目标」「待办」槽位，且总长 ≤ 300 字符 |

**第 5、6 条是核心**。把 `state_bar` 插到 `system` 后面，前缀每轮都变，缓存全废——
而输出读起来完全正常，只是命中率恒为 0。判分器的做法是：同一份 `system`+`history`，
换两个不同的 `state_bar`，前 N 条必须逐字相同。

**第 11–14 条是四家供应商的真实差异**：OpenAI/DeepSeek 用
`prompt_tokens_details.cached_tokens`，Anthropic 用 `cache_read_input_tokens`。
手册的注释说「换供应商只改这一行」——判分器只判 OpenAI 那一套，
但第 13 条（`total=0` 不除零）是共通的：第一轮没有缓存字段，除零会让整个请求崩。

## §3 不判什么

- **缓存命中率真的能到多少**：要真跑两次请求看 `cached_tokens`。
  这里只判**前缀稳定**这个必要条件（不够，但缺了必然命中率 0）。
- **状态栏该放哪些字段**：「目标/已完成/待办/约束」是建议，你放别的也行。
- **历史要不要压缩**：那属于「按需加载」，判分器管不到。

## §4 你的自由

- `state_bar` 的字段与格式
- 是否把 `state_bar` 拆成独立的 `system` 消息（**别**——它就变成前缀的一部分了）
- `cached_ratio` 支持几家供应商
- 返回值用 `dict` 还是 dataclass（判分器按 `dict` 取值，用 dataclass 要能下标/属性取）

## §5 怎么跑

```bash
python3 labs/p3-12/harness/run_checks.py --target ~/code/agentlab-project
python3 labs/p3-12/tools/verify_reference.py
python3 labs/p3-12/tools/self_test.py
```
