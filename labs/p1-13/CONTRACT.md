# P1-13 接口约定（判分只看这一页）

被判对象：`evals/run_eval.py`（你的实现）。
判分器：`harness/run_checks.py`，16 条，无第三方依赖。

```bash
python3 labs/p1-13/harness/run_checks.py --script ~/code/agentlab/evals/run_eval.py
```

判分分两层：**`judge()` 纯函数** 8 条 + **端到端真跑命令** 8 条。
端到端用假 `agentlab` 替掉真模型，不联网、不花钱、结果可复现。

---

## 1. 模块级必须有的纯函数

```python
judge(case: dict, res) -> tuple[bool, str]
```

必须是**模块级**、**无副作用**、**不调 LLM**。
理由不只是好测：判据一旦要模型参与，每次跑分都不一样，评测本身失去意义。

它只能读 `res` 的这四个属性：`status` / `answer` / `steps`（每项有 `name`、`kind`）/ `tool_calls`。

## 2. judge 的四条判据

| 判据 | `case["expect"]` 里的键 | 行为 |
|---|---|---|
| 终止状态 | — | `res.status != "done"` → 直接判红，理由含实际 status |
| 工具选择 | `tools: [名字]` | 缺任何一个 → 红，理由含缺的名字 |
| 工具次数 | `max_tool_calls: int` | 超出 → 红（没有这个键就不检查） |
| 内容 | `must_contain` / `must_not_contain` | **大小写不敏感** |

通过时 `reason` 也不能是空字符串——只看到 PASS 不知道过了什么，排查时等于没有信息。

## 3. 命令行

```bash
python evals/run_eval.py --cases <jsonl> --out <json>
```

| 要求 | 说明 |
|---|---|
| 退出码 | 全部通过 = 0；有任何失败 = **非 0**（这是接 CI 的唯一接口） |
| `--cases` | 逐行 JSON 的测试集，每行至少 `id`、`input`、`expect` |
| `--out` | 写一个 JSON 文件，父目录不存在时自动创建 |

## 4. 输出 JSON 的形状

```jsonc
{
  "summary": {"n": 3, "passed": 2, "rate": 0.667,
              "avg_latency_ms": 1, "by_tag": {"basic": "2/2"}, "failures": ["c3"]},
  "results": [{"id", "passed", "reason", "status", "tool_calls", "latency_ms", "answer", "tags"}]
}
```

- `rate` 保留 3 位小数
- `by_tag` 的值是 `"通过数/总数"` 字符串，给人看的
- `answer` 只落前 300 字：全量答案会让结果文件几十 MB，而且没人会读第二遍
- **单条崩溃不能中断整轮**：崩掉那条记 `passed=false`、`status="error"`，其余照跑

## 5. 判不了的部分

- **你的 prompt 好不好**：那要靠 `eval_results/*.json` 前后对比，人看
- **并发与缓存**：卡正文把它们写成硬要求，但判分不验（验了会强加实现方式）。
  参考实现两样都没做——这是真的缺口，见 NOTES §4
- **LLM judge**：那是 p1-14，本卡只判确定性判据
