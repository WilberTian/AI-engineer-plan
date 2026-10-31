# P5-14 接口约定：特性开关与消融

判分器只看这一页。

## §1 落点与公共名

```
agentlab/flags.py
    Flags            4 个字段（frozen）
        query_rewrite: bool = True
        rerank:        bool = True
        self_check:    bool = False
        cache_prefix:  bool = True
    load(remote: dict[str, bool] | None = None) -> Flags
        优先级：remote > 环境变量 AIP_<字段名大写> > 代码默认

scripts/ablate.py    消融脚本：一次关一个特性，跑同一套测试集，打印差值
```

`scripts/ablate.py` 通过 `agentlab.evals.run_eval(flags=...)` 跑评测，
返回值有 `.pass5` / `.cost` / `.p95` 三个属性。判分器会把它换成一个
**记录每次调用参数的假 eval**（不联网、不花钱）。

## §2 判什么（15 条）

| 组 | # | 断言 |
|---|---|---|
| 开关定义 | 1–2 | 四个字段名与默认值符合上表；`Flags` 不可变（改一个字段会抛异常） |
| 优先级 | 3–5 | `load()` 无参返回默认；remote 优先于环境变量；环境变量优先于默认 |
| 取值语义 | 6–8 | 环境变量只有 `"1"` 算开（`"0"` / `"true"` 都算关）；每个字段都有独立入口；未知 remote key 不让 `load()` 崩 |
| 返回 | 9 | 返回的是 `Flags` 实例 |
| 消融 | 10–12 | 脚本能跑；**每次只关一个**（与默认值相比至多差一个字段）；**每个特性都真的被改过** |
| 消融 | 13 | **基线只算一次**（不是每个特性各算一遍） |
| 输出 | 14–15 | 打印了 Pass@5 与成本；每个特性一行 |

**第 12、13 条是参考实现的缺陷**，见 NOTES §2：

- 第 13 条：`on = run_eval(...)` 写在循环里，基线算了 4 次。不是性能问题，是**统计问题**——
  每次对比用不同基线，delta 里就混进采样噪声，两两之间不可比，而这正是消融要回答的问题
- 第 12 条：`self_check` 默认就是 `False`，所以 `replace(BASE, self_check=False)` 什么都没改。
  这次对比两边一模一样，delta 恒为 0，而你会把它读成「自检没有效果」

**第 6 条为什么严格**：环境变量只有「有/没有」和「值是什么」两种信息。
`"0"` 和 `"false"` 都是非空字符串，`if os.getenv(...)` 会判为真——
所以必须显式比 `== "1"`。这是运维最常踩的一脚：把开关设为 `0`，结果它还是开着。

## §3 不判什么

- **哪个特性真的有用**：那要真跑 eval 的两组对照。这里只判脚本**有没有正确组织**这个对照。
- **AB 分流**：要真实用户，判分器管不到。
- **远程配置从哪来**（HTTP / 文件 / 数据库都行），只判优先级顺序。

## §4 你的自由

- 加字段（判分器会按你的 `Flags` 字段数校验消融覆盖度，不会因为多加字段判错）
- 环境变量前缀（只要不是 `AIP_`，改 CONTRACT §1）
- 消融的输出格式（表格、CSV、JSON 都行，只要含 Pass@5 与成本）

## §5 怎么跑

```bash
python3 labs/p5-14/harness/run_checks.py --target ~/code/agentlab-project
python3 labs/p5-14/tools/verify_reference.py    # 参考实现 14 绿 1 红
python3 labs/p5-14/tools/self_test.py
```

消融部分在临时沙箱里跑（假 eval + 你两份源码的副本），不动你的项目。
需要把项目根目录加进 `PYTHONPATH` 的写法（`pip install -e .`）判分器会自己处理。
