# P2-17 接口约定：用户记忆

判分器只看这一页。

## §1 落点与公共名

```
agentlab/memory.py
    Memory(key: str, value: str, kind: str, source: str)
    upsert(store: dict[str, Memory], m: Memory) -> str     "added" | "noop" | "updated"
    recall(store: dict[str, Memory], query: str, k: int = 5) -> str
    load(path: Path) -> dict[str, Memory]                  文件不存在 → {}
    save(path: Path, store: dict[str, Memory]) -> None
```

`kind` 取值：`preference` / `fact` / `todo`。

## §2 判什么（14 条）

| 组 | # | 断言 |
|---|---|---|
| 写 | 1–3 | 新键→`added`；同值→`noop`；改值→`updated` |
| 冲突 | 4–5 | 同键只有一条且是新值；更新次数可被调用方数出来 |
| 元数据 | 6–7 | `source` / `kind` 不丢 |
| 落盘 | 8–10 | 存盘往返一致（含中文）；文件不存在→`{}`；**跨进程能读到** |
| 读 | 11–14 | **中文查询能召回**；偏好排前；按 k 截断；空库→空串 |

第 10 条用两个子进程跑：第一个写，第二个读。这是卡里第 ① 条要求的「真落盘，不是内存里」。
在同一进程里 `save` 再 `load` 是测不出来的——它可能只是把同一个 dict 传了两次。

第 11 条参考实现是红的，见 §6。

## §3 不判什么

- **卡里第 ③ 条「能说出选这个格式的理由」**：判断，不是代码。
- **卡里第 ④ 条「9 条用例按三层次分别报通过数」**：要真跑模型的三层用例。
- **抽取质量**（从对话里抽出哪条事实）：要真模型。
- **向量检索效果**：参考实现用关键词匹配示意，上生产换向量；判分只看「能不能召回」。

## §4 你的自由

- 存 SQLite / Redis / 文件，只要跨进程能读到
- `recall` 用 jieba / 字符 n-gram / 向量
- `upsert` 返回枚举而不是字符串（但值要对上）
- 加 `ttl` / `confidence` / `last_used_at` 字段

## §5 怎么跑

```bash
python3 labs/p2-17/harness/run_checks.py --target ~/code/agentlab-project
```

## §6 边界：参考实现有 1 条红

```python
hits = [m for m in store.values() if any(w in m.value for w in query.split())]
```

`"我吃辣吗".split()` → `["我吃辣吗"]`（中文没有空格，切不开）。于是 `"我吃辣吗" in "不吃辣"` 恒为 False，
**中文用户永远没有记忆**——而且不报错，测试里也不会红（如果你用英文用例测的话）。

修法三选一：分词（jieba）、字符 n-gram 重叠、双向子串（`w in v or v in w` 再按长度加权）。
