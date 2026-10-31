# P1-3 接口约定：coroutine 与并发

判分器只看这一页。

## §1 落点与公共名

```
scripts/async_demo.py
    async fake_llm(client, idx) -> int      模拟 800ms 的模型延迟，返回 idx
    async serial(n) -> float                n 次串行调用的总耗时
    async concurrent(n) -> float            n 次并发的总耗时
    async with_timeout() -> str             0.3s 超时拦住 1s 的任务
```

`httpx` 由判分器提供替身（本卡的 `fake_llm` 用不到 client，只需要一个能
`async with` 的对象）。

## §2 判什么（13 条）

| 组 | # | 断言 |
|---|---|---|
| 串行 | 1 | `serial(3)` 耗时 ≈ 3×0.8s（落在 [2.0, 3.6]）——串行就是把等待叠加 |
| 并发 | 2–3 | `concurrent(3)` < 1.6s；加速比 ≥ 2.5 |
| 并发 | 4 | `concurrent(1)` 与 `concurrent(3)` 耗时接近（<1.4 倍）——**这才是「真并发」的判据** |
| 顺序 | 5 | 并发时传给 `fake_llm` 的 idx 是 0,1,2 且不重复 |
| 超时 | 6–8 | `with_timeout()` 返回「超时被拦住」；**真的在 1s 内返回**；不返回兜底文案 |
| 静态 | 9–10 | 源码里 async 函数体内没有 `time.sleep`（AST 检查）；并发路径用了 `gather` / `TaskGroup` |
| 复用 | 11 | `serial` 与 `concurrent` 各自只创建一个 client |
| 稳健 | 12–13 | `fake_llm` 原样回传 idx；`gather` 里的异常不被吞掉 |

**第 4 条是这张卡的判据核心**。第 2 条（`concurrent(3) < 1.6`）单独看不够：
把 n 写死成 1 也能过。第 4 条换两个 n，耗时基本不变——这只有真并发才做得到。

**第 9 条为什么要静态查**：`time.sleep` 在 async 函数里会卡住整个事件循环，
表现是「并发写了但一点没快」。它不报错，只是所有协程一起等——这是这张卡
最容易犯、也最难从输出看出来的错。

## §3 不判什么

- **能用真实网络**：夹具的 `fake_llm` 是 `asyncio.sleep`，不碰网络。
- **`asyncio.TaskGroup`（3.11+）与 `gather` 的取舍**：两者都算过（第 10 条）。
- **异常组（ExceptionGroup）的形态**：Python 3.11 的 `TaskGroup` 会把异常包成
  `ExceptionGroup`，判据只要求「异常没被吞」，不限定类型。

## §4 你的自由

- `fake_llm` 的延迟值（只要 ≥0.3s，低于这个数测不出时间差）
- 用 `TaskGroup` 替代 `gather`
- 加信号量限并发（判分器不管上限，但注意别限成 1）
- `with_timeout` 用 `asyncio.wait_for` 而不是 `asyncio.timeout`

## §5 怎么跑

```bash
python3 labs/p1-3/harness/run_checks.py --target ~/code/agentlab-project
python3 labs/p1-3/tools/verify_reference.py
python3 labs/p1-3/tools/self_test.py
```

判分器要真等约 4 秒——时间是这张卡唯一的证据，不能造假替代。
