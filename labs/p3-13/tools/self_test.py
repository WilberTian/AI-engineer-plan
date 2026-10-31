"""判分器体检：把挖矿脚本改坏，对应的检查必须变红。

    python3 labs/p3-13/tools/self_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from refkit import self_test  # noqa: E402

from verify_reference import build  # noqa: E402

MUTATIONS = [
    (
        "去掉按失败类型去重",
        "    if kind in seen:",
        "    if False and kind in seen:",
        "同类失败只留一条",
    ),
    (
        "去掉「反复重试」这条信号",
        '    if r.get("retries", 0) >= 2:',
        '    if False and r.get("retries", 0) >= 2:',
        "按失败类型去重后 5 条",
    ),
    (
        "循环阈值收紧到 >3（正常样本被误报）",
        '    if r.get("tool_calls", 0) > 15:',
        '    if r.get("tool_calls", 0) > 3:',
        "未知类型也收",
    ),
    (
        "expected 用模型自己的输出填上",
        '"expected": "",',
        '"expected": r["final_answer"],',
        "expected 一律留空",
    ),
    (
        "source 标成 manual",
        '"source": "trace"})',
        '"source": "manual"})',
        "source 是 trace",
    ),
    (
        "跑完不报条数",
        'print(f"{len(cases)} 条待填 expected")',
        'print("done")',
        "跑完报出条数",
    ),
    (
        "问题原文被改写",
        '"question": r["input"],',
        '"question": r["input"].strip() + "（复现）",',
        "问题原文照搬",
    ),
]


def main() -> int:
    return self_test(page="stage-p3.html", card="p3-13", lab=LAB, build=build, mutations=MUTATIONS, idx=1)


if __name__ == "__main__":
    sys.exit(main())
