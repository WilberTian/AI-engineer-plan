"""判分器体检：把合规夹具弄坏一处，对应的检查必须变红。

    python3 labs/p1-12/tools/self_test.py
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

KEY = "evals/v1.jsonl"


def _rows(tree):
    return [json.loads(ln) for ln in tree[KEY].splitlines() if ln.strip()]


def _put(tree, rows):
    tree[KEY] = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    return tree


def drop_one(tree):
    return _put(tree, [r for r in _rows(tree) if r["id"] != "t10"])


def should_fail_too_few(tree):
    """t08 变成 happy：只剩 2 条应该失败，全绿幻觉就开始了。"""
    rows = _rows(tree)
    for r in rows:
        if r["id"] == "t08":
            r["tags"] = ["happy", "injection"]
    return _put(tree, rows)


def contradiction(tree):
    rows = _rows(tree)
    rows[0]["expect"]["must_not_contain"] = ["笔记"]
    return _put(tree, rows)


def bad_tool_name(tree):
    rows = _rows(tree)
    rows[0]["expect"]["tools"] = ["search_note"]
    return _put(tree, rows)


def edge_without_assertion(tree):
    rows = _rows(tree)
    for r in rows:
        if r["id"] == "t06":
            r["expect"] = {"tools": ["read_file"]}
    return _put(tree, rows)


def no_edge_group(tree):
    rows = _rows(tree)
    for r in rows:
        if r["id"] in ("t06", "t07"):
            r["tags"] = ["happy", "recover"]
    return _put(tree, rows)


MUTATIONS = [
    ("少一条（9 条）", drop_one, "正好 10 条"),
    ("应该失败的只剩 2 条", should_fail_too_few, "至少 3 条应该失败"),
    ("同一个词既要求出现又要求不出现", contradiction, "断言不矛盾"),
    ("期望了一个不存在的工具名", bad_tool_name, "断言不矛盾"),
    ("edge 用例只留 tools 断言、不给 must_contain", edge_without_assertion, "edge 要求答案里有失败信号"),
    ("edge 那两条改成 happy", no_edge_group, "三类 tag 都有"),
]


def main() -> int:
    return self_test(lab=LAB, tree=fixture(), mutations=MUTATIONS)


if __name__ == "__main__":
    sys.exit(main())
