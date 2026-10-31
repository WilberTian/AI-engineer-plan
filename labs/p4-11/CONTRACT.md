# P4-11 接口约定：四段埋点与分位数

判分器只看这一页。

## §1 落点与公共名

```
agentlab/latency.py
    Timing(t_start=0.0, t_first_token=0.0, t_end=0.0, tool_ms=0.0)
        .ttft_ms -> float        (t_first_token - t_start) * 1000，否则 0
        .gen_ms  -> float        (t_end - t_first_token) * 1000，否则 0
        .total_ms -> float       (t_end - t_start) * 1000
    percentile(values: list[float], p: float) -> float    最近邻，不插值
```

四个时间点用 `time.time()` 或 `time.perf_counter()` 都行，只要同一套。

## §2 判什么（15 条）

| 组 | # | 断言 |
|---|---|---|
| 四段 | 1–3 | ttft / gen / total 各自从时间点算出来（不是存下来的） |
| 退化 | 4–5 | 没设 `t_first_token`（非流式）时 ttft=0、gen=0，**不是把总时长当成 TTFT** |
| 覆盖 | 6 | total 是从开始到结束的全跨度，工具时间在里面 |
| 健壮 | 7 | 时间点乱序（`t_end` 还没记）时不出负值 |
| 派生 | 8 | 改 `t_start` 后 ttft 跟着变（说明是 `@property` 算的） |
| 分位 | 9–15 | 空列表→0；单元素→该值；p0/p100→min/max；奇数 p50 取中；**p95 最近邻不插值**；单调；不改入参 |

第 7 条参考实现是红的：`t_first_token` 记了、`t_end` 还是 0 时，`gen_ms` 算出负数。
这在真实埋点里很常见——计时对象在请求结束前就被读走了。

第 13 条判的是「20 个样本的 p95 必须是 18.0 而不是 18.05」——最近邻 vs 线性插值。
几十条样本时插值出来的小数是假精度。

## §3 不判什么

- **「能回答 p95 是 X ms、最大一段是 Y」**：要真跑 20 条 query，离线判不了。
- **`tool_ms` 怎么归集**：工具时间可能跨多次调用，怎么累加是你的设计。
- **用 wall clock 还是 monotonic**：不判，但用 wall clock 遇到系统时间调整会出怪值（见 NOTES §3）。

## §4 你的自由

- 四个时间点存成 tuple / dict / namedtuple
- `percentile` 加 `interpolate=True` 参数（默认必须是最近邻）
- 加 p99 / 直方图 / 分桶
- 用 `datetime` 而不是 float 秒

## §5 怎么跑

```bash
python3 labs/p4-11/harness/run_checks.py --target ~/code/agentlab-project
```

## §6 边界

15 条判的是算术。它不说明你的延迟报告能回答问题——
「p95 是 X，最大一段是 Y，我把 Z 降了多少」这句话要靠真实跑 20 条 + 改造前后各跑一遍。
