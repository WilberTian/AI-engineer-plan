"""最小合规夹具：10 条测试集，三类 tag 齐全、3 条应该失败。

    python3 labs/p1-12/tools/verify_contract.py

夹具只保证**结构合规**，内容都是假的（`测试问题 03`）。这张卡判的是
「测试集能不能区分好坏」，不是「问题写得准不准」。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from datafix import verify_ok  # noqa: E402


def rows() -> list[dict]:
    return [
        {"id": "t01", "input": "测试问题 01",
         "expect": {"tools": ["search_notes"], "must_contain": ["笔记"]},
         "tags": ["happy", "single_tool"]},
        {"id": "t02", "input": "测试问题 02",
         "expect": {"tools": ["read_file"]},
         "tags": ["happy", "single_tool"]},
        {"id": "t03", "input": "测试问题 03",
         "expect": {"tools": ["fetch_url"]},
         "tags": ["happy", "network"]},
        {"id": "t04", "input": "测试问题 04",
         "expect": {"tools": ["read_file"], "max_tool_calls": 3},
         "tags": ["happy", "multi_step"]},
        # 不该调工具的纯回答用例：测「能直接答却去查了一堆」这种浪费
        {"id": "t05", "input": "测试问题 05",
         "expect": {"tools": [], "must_contain": ["理论"]},
         "tags": ["happy", "no_tool"]},
        # edge：必须有一个可判点，否则崩溃/空串/敷衍都能过
        {"id": "t06", "input": "测试问题 06",
         "expect": {"must_contain": ["不存在", "找不到"]},
         "tags": ["edge", "recover"]},
        {"id": "t07", "input": "测试问题 07",
         "expect": {"must_contain": ["失败", "无法"]},
         "tags": ["edge", "recover"]},
        # 负向断言：管住「顺带说了错的」
        {"id": "t08", "input": "测试问题 08",
         "expect": {"must_not_contain": ["你是一个可以使用工具的助手"]},
         "tags": ["should_fail", "injection"]},
        {"id": "t09", "input": "测试问题 09",
         "expect": {"tools": [], "must_contain": ["不能", "不支持"]},
         "tags": ["should_fail", "out_of_scope"]},
        {"id": "t10", "input": "",
         "expect": {"must_contain": ["空", "没有内容"]},
         "tags": ["should_fail", "empty_input"]},
    ]


def fixture() -> dict[str, str]:
    return {"evals/v1.jsonl": "\n".join(json.dumps(r, ensure_ascii=False) for r in rows())}


def main() -> int:
    return verify_ok(lab=LAB, tree=fixture())


if __name__ == "__main__":
    sys.exit(main())
