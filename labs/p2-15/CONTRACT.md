# P2-15 接口约定：一个工具的描述规格

判分器只看这一页。判的是 `search` 这一个工具——`read` / `answer` 用同一套要求自查。

## §1 落点

```
tools/search.json          一个工具的规格，JSON 对象
```

三个顶层键，缺一不可：`name` / `description` / `parameters`。

```json
{"name": "search",
 "description": "何时用：… 何时别用：… 返回：… 搜不到时：…",
 "parameters": {"type": "object", "properties": {…}, "required": ["query"],
                "additionalProperties": false}}
```

## §2 判什么（14 条）

| 组 | # | 断言 |
|---|---|---|
| 结构 | 1–3 | JSON 可解析且是对象；三个顶层键都在；`name` 是小写动词名 |
| 名字 | 4 | **没有按后端接口拆的痕迹**：不含 `_by_`、`get_`、`list_`、`chunk`——那是「切在接口上」的签名 |
| 描述 | 5–8 | 长度 ≥ 80 字；含「何时用」；含「何时别用」；含「返回」 |
| 描述 | 9 | 不含 `...` / `TODO` 这类占位符 |
| 参数 | 10–12 | `parameters.type` 是 `object` 且有 `properties`；`required` 非空且每一项都在 `properties` 里；每个参数都有 `description` |
| 收紧 | 13–14 | `additionalProperties` 为 `false`；参数不超过 6 个 |

**为什么名字那条要判**：`search_by_title` / `search_by_date` / `get_chunk` / `list_docs`
这四个名字一出现，说明工具是照着后端接口切的。工具一多，模型选错的概率立刻上升。
切法应该是**按用户目标**——标题、日期、来源、文档类型全收进 `filters` 参数。

**为什么「何时别用」是硬要求**：只写「搜索文档」等于没写，模型只能靠名字猜。
反例段是唯一能阻止模型「明明能直接答却去搜一遍」的东西，而那是线上最常见的浪费。

## §3 不判什么

- **描述写得好不好读**：措辞、语气、中文还是英文，都行。
- **工具切得对不对**：`search`/`read`/`answer` 这个三分布是卡里的建议，你切四个也可以。
  判分器只看这一个工具的**描述质量**。
- **模型会不会因为描述变好而选对**：那要真跑，属于 P2-13 的指标。

## §4 你的自由

- 参数怎么设计（只要每个都有 `description`，且不超过 6 个）
- `filters` 里放哪些枚举（`doc_type` / `date_from` / `source` 都是常见项）
- 是否加 `examples` 字段（判分器不管额外键）

## §5 怎么跑

```bash
python3 labs/p2-15/harness/run_checks.py --target ~/code/agentlab-project
python3 labs/p2-15/tools/verify_contract.py
python3 labs/p2-15/tools/self_test.py
```
