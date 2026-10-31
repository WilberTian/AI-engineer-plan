"""最小合规夹具：按 CONTRACT 的分布造 30 条，证明判据是可满足的。

    python3 labs/p2-12/tools/verify_contract.py

这里不引用手册里的样例数据——那是一行格式说明。夹具只保证**结构合规**：
五类条数对得上、字段齐全、多跳跨两段。内容当然是假的（`事实问题 03`），
因为这张卡判的是分布，不是题目质量。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from datafix import verify_ok  # noqa: E402

DIST = {"fact": 12, "multi_hop": 6, "precise": 4, "unanswerable": 6, "injection": 2}
LABEL = {
    "fact": "事实问题",
    "multi_hop": "多跳问题",
    "precise": "精确串问题",
    "unanswerable": "不可答问题",
    "injection": "注入问题",
}


def rows() -> list[dict]:
    out = []
    n = 0
    for kind, count in DIST.items():
        for k in range(1, count + 1):
            n += 1
            base = {"id": f"v2-{n:02d}", "type": kind,
                    "question": f"{LABEL[kind]} {k}：这条问的是什么？"}
            if kind == "unanswerable":
                base.update(gold_answer="", gold_snippets=[], must_refuse=True)
            elif kind == "multi_hop":
                base.update(gold_answer=f"第 {k} 条由两段拼出来的答案",
                            gold_snippets=[f"doc-{k}-a.md#1", f"doc-{k}-b.md#2"],
                            must_refuse=False)
            else:
                base.update(gold_answer=f"第 {k} 条的原文答案",
                            gold_snippets=[f"doc-{k}.md#3"], must_refuse=False)
            out.append(base)
    return out


def fixture() -> dict[str, str]:
    return {"evals/rag_v2.jsonl": "\n".join(json.dumps(r, ensure_ascii=False) for r in rows())}


def main() -> int:
    return verify_ok(lab=LAB, tree=fixture())


if __name__ == "__main__":
    sys.exit(main())
