# P4-8 接口约定：成本记账

判分器只看这一页。

## §1 落点与公共名

```
agentlab/cost.py
    PRICES: dict[str, dict[str, float]]      {"模型名": {"in": …, "out": …, "cached_in": …}}，单位美元/百万 token
    Usage(model: str, input_tokens=0, output_tokens=0, cached_tokens=0)
        .cost_usd() -> float
    summarize(usages: list[Usage]) -> dict  含 total_usd / input_tokens / output_tokens / cache_hit_rate / n_calls
```

价格填什么由你定，判分**读你自己的 `PRICES`** 算期望值，不锁死具体数字。

## §2 判什么（16 条）

| 组 | # | 断言 |
|---|---|---|
| 单位 | 1–4 | 0 token → 0；纯输入/纯输出按百万 token 单价；**100 万 input 正好等于单价** |
| 缓存 | 5–7 | 命中部分**从 input 扣掉**再按 `cached_in` 算；全命中只算缓存价；`cached > input` 不出负成本 |
| 缺价 | 8–9 | 未知模型返回 0.0（不猜）；不抛异常 |
| 线性 | 10 | 三倍用量 = 三倍成本 |
| 汇总 | 11–16 | 总额 = 逐条之和；in/out 合计；命中率 = cached/input；空列表不除零；`n_calls` 数调用；不改入参 |

**第 4 条是最容易错的一条**：单价表写着「美元/百万 token」，除数却写成 `/1000`，成本虚高 1000 倍。
线性检查抓不到这个错（三倍还是三倍），只有绝对值和「100 万 token 应正好等于单价」能抓。

**第 5 条是最值钱的一条**：不把 `cached_tokens` 从 `input_tokens` 里减掉，同一批 token 会被算两遍，
命中率越高、成本算得越离谱——而且方向是**反向**的，你会得出「缓存没用」的结论。

## §3 不判什么

- **「能说出成本里 X% 来自输入 token」**：要真跑一次 eval 拿到 usage，离线判不了。
- **价格表对不对**：各厂商价格会变，判分不核对。但第 4 条会保证单位换算没错。
- **`cached_tokens` 怎么拿**：有的厂商在 `usage.prompt_tokens_details.cached_tokens`，有的没有。拿不到记 0 是对的（手册「卡住怎么办」里写了）。

## §4 你的自由

- 用 `Decimal` 而不是 float
- `PRICES` 从 YAML / 数据库读
- `summarize` 返回 dataclass 而不是 dict（但键名要对上，判分读键）
- 加 `p95_latency` 之类额外字段

## §5 怎么跑

```bash
python3 labs/p4-8/harness/run_checks.py --target ~/code/agentlab-project
```

## §6 边界

16 条全绿说明**算术对了**。它不说明你的成本结构健康——那要看一次真实 eval 的报告，
看输入 token 占比、缓存命中率、哪一步最贵。这部分只能真跑。
