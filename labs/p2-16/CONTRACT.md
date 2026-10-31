# P2-16 接口约定：通过率之外的指标

判分器只看这一页。

## §1 落点与公共名

```
evals/metrics.py
    Run(task_id: str, ok: bool, steps: list[dict] = [])
        steps 每项：{"tool": str, "args": dict, "result": str, "error": str}

    pass_at_k(runs: dict[str, list[bool]], k: int) -> float
    pass_pow_k(runs: dict[str, list[bool]], k: int) -> float
    attribute(run: Run) -> str                      形如 "step0:tool_error" / "final:answer_format" / "ok"
    boot_ci(xs: list[float], n: int = 2000) -> tuple[float, float]
    paired_delta(a: dict[str, bool], b: dict[str, bool]) -> tuple[int, int]
    tally(cases: list[dict], before: dict[str, bool], after: dict[str, bool]) -> dict[str, int]
        tally 的键：held / fixed / regressed / still_broken
```

## §2 判什么（16 条）

| 组 | # | 断言 |
|---|---|---|
| pass@k / pass^k | 1–5 | pass@k 任一次成功；**只看前 k 次**；pass^k 连续 k 次；**次数不足不算成功**；两指标对同一批数据必须给出不同值 |
| 失败归因 | 6–10 | 工具错误 → `tool_error`；调了没结果 → `bad_args`；**归到第一个失败环节**；步骤都对但答案不合格 → `final`；成功 → `ok` |
| 显著性 | 11–13 | bootstrap 区间包住中位数；`paired_delta` 只数单边翻转；两边一致的不计入 |
| 四态 | 14–16 | 四态计数正确；**regressed 单独报**；四态之和 = case 数 |

第 5 条是这页最值得理解的断言：**同一批数据下 `pass@3` 和 `pass^3` 必须给出不同的值**。
如果两个数一样，说明你其实只算了一个指标，另一个是它的复读。

第 16 条抓的是漏 case：四态之和必须等于 case 数。少一个 case 你发现不了——
除非你每天盯的是「regressed」这个数，而它恰好漏掉了。

## §3 不判什么

- **跨模型显著性**：要真跑两组 eval（同一批 case、两个模型），离线判不了。
- **`boot_ci` 的随机性**：参考实现用全局 `random.choice`，同一份数据两次结果会略有不同。这是实现选择，不是错——判分只查区间合理性。要严格可复现就传固定种子。
- **归因分类的完备性**：真实失败可能有「检索到错文档」这种层面，`attribute` 只看 steps。

## §4 你的自由

- `attribute` 返回 `(step_idx, reason)` 元组而不是字符串
- `pass_at_k` 接受 `list[bool]` 而不是 dict（但要保持按 task 分组）
- `tally` 多加一态（比如 `flaky`）
- `boot_ci` 换 `statistics.quantiles`

## §5 怎么跑

```bash
python3 labs/p2-16/harness/run_checks.py --target ~/code/agentlab-project
```

## §6 边界

16 条判的是**定义**。它不判「你的 eval 有没有代表性」——
那取决于你的 30 条 case 怎么来的，判分器不知道你的语料。
