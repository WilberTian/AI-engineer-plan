# P1-12 接口约定：10 条测试集

判分器只看这一页。

## §1 落点

```
evals/v1.jsonl            10 行 JSONL，一行一条
```

每行：

```json
{"id": "t01", "input": "…", "expect": {"tools": ["search_notes"], "must_contain": ["asyncio"]},
 "tags": ["happy", "single_tool"]}
```

`expect` 里可以出现的键：

| 键 | 含义 |
|---|---|
| `tools` | 期望调用的工具序列（子集匹配，空列表 = 不该调工具） |
| `must_contain` | 最终答案里必须出现的词（任一命中即可） |
| `must_not_contain` | 最终答案里不许出现的词 |
| `max_tool_calls` | 工具调用次数上限 |

`tags` 第一段必须是 `happy` / `edge` / `should_fail` 之一——这三段决定「通过率怎么分组报」。

工具名只有三个：`search_notes` / `read_file` / `fetch_url`（P1-9 的注册表）。

## §2 判什么（13 条）

| 组 | # | 断言 |
|---|---|---|
| 文件 | 1–3 | 每行可解析；正好 10 条；无空行 |
| 字段 | 4–6 | `id` 唯一且形如 `tNN`；`input`/`expect`/`tags` 都在；`expect` 的键只用上表四个 |
| 分组 | 7–9 | 三类 tag 都有；**`should_fail` 至少 3 条**；`should_fail` 里必须有 `injection` 和 `out_of_scope` |
| 可判性 | 10–13 | 至少一条「不该调工具」的 happy 用例；至少一条带 `must_not_contain` 的负向断言；`edge` 用例的 `must_contain` 非空；`must_contain` 与 `must_not_contain` 不互相矛盾 |

**为什么「至少 3 条应该失败」是硬指标**：全是能通过的测试集会给你虚假的安全感。
一个 10 条全绿的评测报告和一个 7 绿 3 红改到 10 绿的报告，信息量完全不同。

**为什么 `edge` 必须有 `must_contain`**：`读 notes/nonexist.md` 这种用例，
如果只写 `tools: ["read_file"]`，那么 agent 崩溃、返回空串、返回「好的我读了」
都能过。必须有一个词来区分「处理了错误」和「没处理」。

## §3 不判什么

- **用例选得好不好**：「这条问题值不值得测」是判断，不是断言。
- **通过率**：那要跑真模型，是 P1-13 的事。这里只判测试集本身。
- **`input` 的措辞**：中文、英文、带不带标点都行。

## §4 你的自由

- 多于 10 条（判据是「正好 10 条」——想扩到 30 条改 CONTRACT，那是 P2-12）
- 加自定义 tag（`tools` 之外的第三段，如 `network`、`multi_step`）
- 工具清单（如果你的注册表不止三个，改 CONTRACT §1 的清单）

## §5 怎么跑

```bash
python3 labs/p1-12/harness/run_checks.py --target ~/code/agentlab-project
python3 labs/p1-12/tools/verify_contract.py    # 合规夹具必须全绿
python3 labs/p1-12/tools/self_test.py          # 弄坏必须红
```
