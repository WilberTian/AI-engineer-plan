# P3-13 接口约定：从 trace 挖失败样本

判分器只看这一页。

## §1 落点

```
evals/mine_failures.py     挖矿脚本：读 logs/runs.jsonl，写 evals/v2.jsonl
logs/runs.jsonl            输入（判分器会铺一份 9 条的夹具）（P3-11 的产出）
evals/v2.jsonl             输出：挖出来的样本，一人一行
```

`evals/v2.jsonl` 每行五个键：

```json
{"id": "mined-<run_id 前 8 位>", "question": "…", "expected": "",
 "actual": "…", "source": "trace"}
```

**`expected` 必须是空串**——这是整张卡的观点：模型不能自己填标准答案。

## §2 判什么（13 条）

| 组 | # | 断言 |
|---|---|---|
| 能跑 | 1–2 | 脚本退出码 0；产出文件存在且每行可解析 |
| 挖到 | 3–6 | 按失败类型去重后**正好 5 条**；四种信号都命中（`error` / `retries≥2` / `tool_calls>15` / `user_score<0.5`）；同类失败只留一条；**没有 `error_type` 的那条也要收**（记为 unknown） |
| 不误报 | 7 | 正常的 run 不许被挖出来 |
| 格式 | 8–12 | `expected` 一律空；`id` 唯一且带 `mined-` 前缀；`source` 是 `trace`；`question` 原文照搬；`actual` 保留当时回答 |
| 提示 | 13 | 跑完打印「N 条待填 expected」 |

**为什么要判「不误报」**：误报比漏报更伤。漏报只是少一条，
误报是把「本来是对的」写进失败集——你按这个集合去改，改的是不存在的 bug。

**为什么 13 条判「打印条数」**：这一步的产出是「N 条等人填」，
挖完不报个数，这件事就会被忘掉。判分器把「报数」当交付的一部分。

## §3 不判什么

- **`expected` 填得对不对**：这必须人判，而且**判分器永远不判**——
  一旦能自动判，就会有人用模型去填，然后整张卡的意义消失。
- **去重粒度该多细**：按 `error_type`、按「错误 + 工具名」、按嵌入聚类都行。
  判分器只要求「timeout 出现两次 → 留一条」。
- **挖矿阈值**（`retries ≥ 2` / `tool_calls > 15` / `score < 0.5`）：这些是手册给的初值，
  你的系统该自己定。判分器只要求「四种信号都在起作用」。

## §4 你的自由

- 阈值怎么定
- 是否加更多信号（空回复、拒答率异常、延迟超阈）
- 去重的 key（只要同类失败只留一条）
- 输出里加额外字段（`error_type`、`run_id` 原文都可以）

## §5 怎么跑

```bash
python3 labs/p3-13/harness/run_checks.py --target ~/code/agentlab-project
python3 labs/p3-13/tools/verify_reference.py   # 参考实现全绿
python3 labs/p3-13/tools/self_test.py
```

判分器**不会动你的文件**：它把 `evals/mine_failures.py` 拷到一个临时沙箱，
铺上夹具日志，在那里跑。你在项目里已经填了 `expected` 的 `evals/v2.jsonl`
不会被覆盖——那是你人判劳动的唯一副本。
