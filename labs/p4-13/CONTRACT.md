# P4-13 接口约定：成本分解表

判分器只看这一页。

## §1 落点与公共名

```
scripts/breakdown.py            （放项目根目录也认）
    COST_IN, COST_OUT: float    美元 / token
    breakdown(trace) -> list[tuple[str, float, int]]
        trace.spans 里每个 span 有：kind / name / in_tok / out_tok / ms
        返回按成本降序的 (name, cost, ms)
```

`trace` 的形状：`SimpleNamespace(spans=[...])`，判分就是这么造的。你的真实 trace 只要有
`.spans` 和这四个字段就能用。

## §2 判什么（12 条）

| # | 断言 |
|---|---|
| 1 | 成本 = `in_tok×COST_IN + out_tok×COST_OUT` |
| 2–3 | 同名 span 合并成本、累加耗时（一个 run 里 `self_check` 会被调很多次） |
| 4 | 按成本降序（分解表的意义就是「先看最大的一行」） |
| 5 | 工具 span 不按 token 计价（执行工具不烧 token） |
| 6 | **检索/重排 span 不被静默丢掉**（卡里明确要求拆到这两类） |
| 7–9 | 空 trace→[]；全工具 span 不崩；单 span 正常 |
| 10–12 | 不改入参；同一输入结果一致；零 token 不除零 |

第 6 条参考实现是红的：`if s.kind != "llm": continue` 直接把检索和重排丢了。
成本记 0 没关系，但**名字要出现在表里**——否则你会得出「钱全在模型上」这个假结论，
而延迟的大头可能在重排。

## §3 不判什么

- **那道面试题本身**：25 分钟讲完、四步顺序（分解→定位→三杠杆→回归）。考的是决策顺序，不是代码。
- **单价填得对不对**：`COST_IN`/`COST_OUT` 由你按自己模型填，判分读你的值。
- **真实 trace 的接入**：判分用假 trace，你的 OpenTelemetry/Langfuse span 长什么样不管。

## §4 你的自由

- 返回 dict 而不是三元组列表（但判分读 tuple，见 §1）
- 加 `share` 字段（占比）
- 按 `kind` 分组再按名字分组（两级）
- 输出成 CSV/JSON 而不是 print

## §5 怎么跑

```bash
python3 labs/p4-13/harness/run_checks.py --target ~/code/agentlab-project
```

## §6 边界

12 条判的是分解表算得对不对。它不判你**会不会用**这张表——
那道题的杀伤力在「先量后改」，而这件事没有判分器能测。
