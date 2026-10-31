# P1-2 要点核对表：结构化输出的边界

行号锚点：`stage-p1.html#p1-2` 的代码块，**23 行，sha256 `175d0a6a478e88a6`**。
`tools/verify_reference.py` 每次会打印当前 sha。

先跑 `harness/run_checks.py`，再回来看这张表。

---

## 1. 决策点

| # | 位置 | 参考实现的选择 | 另一种合理选择 | 什么时候该换 | 怎么核你那份 |
|---|---|---|---|---|---|
| 1 | L13 `confidence` | `Literal["high","medium","low"]` | `enum.StrEnum` | 需要 `.value` 做展示映射时 | 看 `model_json_schema()` 里有没有 `enum` |
| 2 | L14 `citations` | `Field(default_factory=list)` | `= []`（pydantic v2 会自动深拷贝） | 不需要换，但别依赖 v1 的行为 | 建两个实例，`a.citations is not b.citations` |
| 3 | L15 `refused` | 独立布尔字段 | 去掉它，用 `citations == []` 推断 | 需要区分「拒答」和「答了但没引用」时 | 看你能不能表达「有引用但我不确定」 |
| 4 | L8 `quote` 上限 | `max_length=300` | 按 token 而非字符限制 | 引用大量英文时字符数≠token 数 | 301 字应被拒 |
| 5 | L12 `answer` 描述 | 「没有依据时必须为空字符串」 | 不约束，允许随意填 | 从不——模型会照描述填 | 看描述里有没有写清空值的条件 |
| 6 | 业务规则 | `field_validator("citations")` | `model_validator(mode="after")` | **必须换**，见 §4 | 见 §4 的两条复现 |
| 7 | 校验方式 | 运行时校验，转换 `"1"→1` | `ConfigDict(strict=True)` 拒绝转换 | 需要「模型返回字符串就报错」而不是静默转 | 传 `confidence=1`，看是转还是拒 |

## 2. 静默错误

| # | 现象 | 为什么危险 |
|---|---|---|
| 1 | **默认值不走 validator** | `citations` 不传时规则整条失效。模型最常做的事恰恰是不返回这个键 → 坏数据全放行，且不报错（§4） |
| 2 | **`info.data` 只有已校验的前序字段** | `citations` 在 `refused` 之前，validator 里读不到 `refused` → 明确拒答被误杀（§4） |
| 3 | `Literal` 写成 `str` 不报错 | schema 里没有 `enum`，结构化输出时模型不受约束，非法值到运行时才炸 |
| 4 | `Optional[str]` 不给默认值 | pydantic v2 里它**是必填的**，`None` 要显式传。和 TS 的 `a?:` 语义不同 |

## 3. 判分器判不了的部分

- 模型会不会真的按 schema 返回（要真调用，P1-5/P1-6）
- schema 好不好用：只能靠 P1-6「连续 10 次都通过」

---

## 4（重点）：参考实现自身不达标的两条

手册 p1-2 当前的代码，**业务规则在两个方向上都错了**。这是实测，不是推测——
`tools/verify_reference.py` 会稳定复现这两条。

### 4.1 该拒的放过了：默认值不校验

```
Answer(answer="答", confidence="high")        # 没有 citations 键
→ 通过，citations=[]
```

原因：`@field_validator("citations")` 默认只在**该字段被赋值**时运行。
`citations` 走 `default_factory` 时 validator 被跳过，规则完全没执行。

模型的真实输出里通常**根本没有** `citations` 这个键，所以这是最常见的一格。

### 4.2 该放的误杀了：`info.data` 里没有 `refused`

```
Answer(answer="", confidence="low", citations=[], refused=True)   # 明确拒答
→ 被拒：「非拒答回答必须至少有一条引用」
```

原因：字段顺序是 `answer → confidence → citations → refused`。
校验 `citations` 时，`refused` 还没校验，`info.data` 里查不到，`.get("refused", False)` 取到 `False`。

### 4.3 怎么修

把 `field_validator` 换成 `model_validator(mode="after")`——它拿到的是整个模型实例，
两个问题一起解决：

```python
from pydantic import BaseModel, Field, model_validator

    @model_validator(mode="after")
    def need_citation_unless_refused(self):
        if not self.citations and not self.refused:
            raise ValueError("非拒答回答必须至少有一条引用")
        return self
```

`tools/self_test.py` 就是用这个修正版当基线，再往里塞 bug 验证判分有效。

### 4.4 为什么还留着这个洞

这两个洞正好是这张卡要你自己想清楚的地方：**校验器在什么时机运行、它能看到什么**。
手册里 `p1-2` 的「卡住怎么办」已经写了「字段顺序有影响」，只是代码没跟上。

修不修手册由维护者决定；`verify_reference.py` 在修好之后会报「已知偏差不再失败」并提示删掉对应条目。
