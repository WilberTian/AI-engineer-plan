# P2-10 接口约定：拒答的两层判据

判分器只看这一页。

## §1 落点与公共名

```
agentlab/rag/answer.py
    REFUSE: str                                  固定拒答文案
    answer(question: str, top_score: float, chunks: list) -> tuple[str, str]
        返回 (回复文本, 原因)，原因只允许三种：
            "refused_low_score"   第一层：分数/证据不足
            "refused_by_model"    第二层：模型自己判断资料不够
            "answered"            正常回答
```

`llm` / `SYSTEM_WITH_REFUSE_RULE` / `USER_TMPL` 由外部提供（手册那段是节选）。

## §2 判什么（13 条）

| 层 | # | 断言 |
|---|---|---|
| 第一层 | 1 | `chunks` 为空 → 拒答，且**一次模型都没调**（省下的是钱也是延迟） |
| 第一层 | 2–4 | `top_score` 低于阈值 → 拒答且不调模型；**0.34 拒、0.35 放行**（`<` 不是 `<=`） |
| 第二层 | 5–6 | 模型回答里出现「资料中没有」或「无法回答」→ 转成 `refused_by_model` |
| 第二层 | 7 | 正常回答 → 原文返回，原因 `answered` |
| 两层都要有 | 8–9 | 两种拒答的**原因可区分**，但**文案是同一句** `REFUSE` |
| 第二层 | 10 | 调模型时 system 段带拒答规则、user 段带问题（否则第二层等于没设） |
| 稳健 | 11–13 | 空问题不崩；模型返回空串**不算答好**；返回值是二元组且原因在白名单内 |

**阈值 0.35 是卡里写的数**，实际值要你用 W09 的 unanswerable 集定。
判分器只卡「`<` 而不是 `<=`」——边界挪一格不报错，只是多拒一档或漏拒一档，你永远看不出来。

**为什么「空 chunks 不调模型」单独判**：这是硬门槛的全部意义。
只写 prompt 说「资料不足就说不知道」，模型仍然会尽力回答；
而硬门槛的价值是**在花钱之前就拦住**。

## §3 不判什么

- **阈值该定多少**：要靠 unanswerable 集跑分布，离线判不了（CONTRACT 只卡 0.35 这个手册值）。
- **过度拒答**：要真跑 12 条 answerable 看拒了多少。
- **模型会不会老实说不知道**：那是模型行为，第二层只是「给出口」。
- **第 12 条**：参考实现**不达标**（模型返回空串时它判 `answered`），见 NOTES §2。

## §4 你的自由

- 阈值来源（常量、配置、按 query 类型分档都行）
- 第二层的识别方式（关键词、结构化输出、`finish_reason`）
- 是否加第三层（引用校验：答案里的引用是否真在 chunks 里）

## §5 怎么跑

```bash
python3 labs/p2-10/harness/run_checks.py --target ~/code/agentlab-project
python3 labs/p2-10/tools/verify_reference.py   # 参考实现 12 绿 1 红
python3 labs/p2-10/tools/self_test.py
```
