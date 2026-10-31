"""判分器体检：把合规夹具弄坏一处，对应的检查必须变红。

    python3 labs/p2-12/tools/self_test.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from datafix import self_test  # noqa: E402

from verify_contract import fixture  # noqa: E402

KEY = "evals/rag_v2.jsonl"


def _rows(tree: dict[str, str]) -> list[dict]:
    return [json.loads(ln) for ln in tree[KEY].splitlines() if ln.strip()]


def _put(tree: dict[str, str], rows: list[dict]) -> dict[str, str]:
    tree[KEY] = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    return tree


def drop_one(tree):
    rows = _rows(tree)
    return _put(tree, [r for r in rows if r["id"] != "v2-12"])


def shift_type(tree):
    """总数不变，但从 precise 挪一条到 fact——分布变了，平均数就被某一类主导。"""
    rows = _rows(tree)
    for r in rows:
        if r["type"] == "precise":
            r["type"] = "fact"
            break
    return _put(tree, rows)


def unanswerable_not_refuse(tree):
    rows = _rows(tree)
    for r in rows:
        if r["type"] == "unanswerable":
            r["must_refuse"] = False
            break
    return _put(tree, rows)


def multi_hop_single_source(tree):
    rows = _rows(tree)
    for r in rows:
        if r["type"] == "multi_hop":
            r["gold_snippets"] = r["gold_snippets"][:1]
            break
    return _put(tree, rows)


def placeholder_answer(tree):
    rows = _rows(tree)
    for r in rows:
        if r["type"] == "fact":
            r["gold_answer"] = "..."
            break
    return _put(tree, rows)


def duplicate_id(tree):
    rows = _rows(tree)
    rows[1]["id"] = rows[0]["id"]
    return _put(tree, rows)


MUTATIONS = [
    ("少一条（29 条）", drop_one, "正好 30 条"),
    ("从 precise 挪一条到 fact（总数不变）", shift_type, "每类条数对得上"),
    ("不可答的 must_refuse 改成 false", unanswerable_not_refuse, "不可答都标了拒答"),
    ("多跳只留一段出处", multi_hop_single_source, "多跳至少跨两段"),
    ("gold_answer 写成占位符 ...", placeholder_answer, "没有占位符"),
    ("两条 id 撞车", duplicate_id, "id 唯一且格式统一"),
]


def main() -> int:
    return self_test(lab=LAB, tree=fixture(), mutations=MUTATIONS)


if __name__ == "__main__":
    sys.exit(main())
