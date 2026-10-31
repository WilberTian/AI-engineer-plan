# P2-12 接口约定：30 条测试集的分布与字段

判分器只看这一页。

## §1 落点

```
evals/rag_v2.jsonl        30 行 JSONL，一行一条
```

每行的字段（六个，缺一不可）：

```json
{"id": "v2-07", "type": "multi_hop", "question": "…", "gold_answer": "…",
 "gold_snippets": ["…", "…"], "must_refuse": false}
```

`type` 只允许五种，且**数量是卡里定死的**：

| type | 条数 | 测什么 |
|---|---|---|
| `fact` | 12 | 单点检索 + 准确复述 |
| `multi_hop` | 6 | 跨段拼接、不遗漏条件 |
| `precise` | 4 | 专有名词 / 错误码 / 版本号 |
| `unanswerable` | 6 | 拒答正确性 |
| `injection` | 2 | 语料里的「忽略指令」会不会把 agent 带走 |

## §2 判什么（14 条）

| 组 | # | 断言 |
|---|---|---|
| 文件 | 1–3 | 每行可解析；正好 30 行；无空行 |
| 字段 | 4–6 | 六个字段都在；`id` 唯一且形如 `v2-NN`；`question` 不重复 |
| 类型分布 | 7–9 | 五类都有；**每类条数与上表一致**；没有第六种类型 |
| 语义 | 10–13 | `unanswerable` → `must_refuse=true` 且 `gold_snippets` 为空；其余类 → `must_refuse=false`；`multi_hop` 的 `gold_snippets` ≥2（单源不叫多跳）；`fact`/`precise` 的 `gold_snippets` ≥1 |
| 防抄样例 | 14 | 全文不出现 `...` / `…` 这类占位符，`gold_answer` 非空且不等于 `question` |

**为什么条数要卡死**：分布变了，通过率的含义就变了。30 条里 20 条是 `fact`，
总通过率就会被这一类主导——你看到的 0.8 可能只是「事实型还行」，
而 `multi_hop` 六条全错也会被平均数盖住。**分类型报通过率的前提是分类型的条数固定。**

## §3 不判什么

- **`gold_answer` 抄得对不对**：这需要人对着语料核。判分器只查「非空、不是占位符、不等于问题」。
- **`question` 是不是真从语料里问得出来**：卡里验收要求「每条 gold_answer 是从语料里抄的、不是自己编的」，离线判不了。
- **`injection` 那两条能不能真扛住**：要真跑模型。

## §4 你的自由

- `id` 的编号方式（只要唯一且可追溯）
- 是否多加字段（`source`、`difficulty`、`tags` 都可以）
- 语料主题（文档库、政策库、自己的笔记都行）

## §5 怎么跑

```bash
python3 labs/p2-12/harness/run_checks.py --target ~/code/agentlab-project
python3 labs/p2-12/harness/run_checks.py --target . --filter multi_hop
```
