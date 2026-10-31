# P1-2 接口约定（判分只看这一页）

被判对象：`src/agentlab/schema.py`（你的实现）。
判分器：`harness/run_checks.py`，12 条。**需要 pydantic**（你项目里本来就有）。

```bash
uv run python labs/p1-2/harness/run_checks.py --target ~/code/agentlab/src
```

没装 pydantic 时判分器会明确报「判不了」并退出码 2，不会假装通过。

---

## 1. 必须提供的名字

| 名字 | 要求 |
|---|---|
| `Citation` | `BaseModel` 子类 |
| `Answer` | `BaseModel` 子类 |

两个类的字段名和约束**以手册 p1-2 的映射表为准**，这里是判分要验的部分：

| 字段 | 约束 |
|---|---|
| `Citation.doc_id` | `str`，不允许 `None` |
| `Citation.quote` | 长度 1–300 |
| `Answer.answer` | `str` |
| `Answer.confidence` | `Literal["high","medium","low"]`（**必须是枚举**，不是 `str`） |
| `Answer.citations` | `list[Citation]`，默认空，**实例之间不能共享** |
| `Answer.refused` | `bool`，默认 `False` |

## 2. 业务规则（这张卡的真正考点）

> **要么有引用，要么明确拒答。两者都不满足就是坏数据。**

它对两类输入的行为必须**一致**：

| 输入 | 期望 | 为什么单列 |
|---|---|---|
| `citations=[]` + `refused=False` | 拒 | 显式传空列表 |
| **不传** `citations` + `refused=False` | **拒** | 模型的真实输出里通常根本没有这个键 |
| `citations=[]` + `refused=True` | **过** | 拒答本来就没有引用 |
| 不传 `citations` + `refused=True` | **过** | 同上 |

后三行是这份约定的重点：很多实现只在「显式传空列表」时生效，或者把「明确拒答」也误杀。
**这两种都属于判分器会标红的错**，原因见 NOTES §4。

## 3. 报错要能定位

所有坏数据都必须抛 `ValidationError`，且 `exc.errors()[0]["loc"]` 非空、能指到出问题的字段。
`loc` 为空意味着你 debug 时只能靠猜。

## 4. 判不了的部分

- **模型实际会不会返回这种 JSON**：要真调用，属 P1-5/P1-6 的事
- **schema 写得好不好**（字段名对模型友不友好）：只能靠 P1-6 的「连续 10 次都通过」验证
