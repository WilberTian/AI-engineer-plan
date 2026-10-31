"""判分器体检：往 metrics.py 里塞已知定义错。

    python3 labs/p2-16/tools/self_test.py

7 个 mutation 全是「算得出数、但数是错的」那类——它们不报错，只会悄悄改变结论。
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
        "pass@k 看全部运行（不限制 k）",
        "    return sum(1 for rs in runs.values() if any(rs[:k])) / len(runs)",
        "    return sum(1 for rs in runs.values() if any(rs)) / len(runs)",
        "pass@k 只看前 k 次",
    ),
    (
        "pass^k 不检查运行次数够不够",
        "    return sum(1 for rs in runs.values() if len(rs) >= k and all(rs[:k])) / len(runs)",
        "    return sum(1 for rs in runs.values() if all(rs[:k])) / len(runs)",
        "运行次数不足时不算 pass^k",
    ),
    (
        "归因到最后一个失败环节",
        "    for i, s in enumerate(run.steps):",
        "    for i, s in reversed(list(enumerate(run.steps))):",
        "归因到第一个失败环节",
    ),
    (
        "步骤都对时也归成工具错误",
        '    if not run.ok:\n        return "final:answer_format"              # 步骤都对，答案表达不合格',
        '    if not run.ok:\n        return "step0:tool_error"',
        "步骤都对但答案不合格时归到 final",
    ),
    (
        "delta 把两边都对的也算进去",
        "    a_only = sum(1 for t in a if a[t] and not b.get(t))",
        "    a_only = sum(1 for t in a if a[t])",
        "paired_delta 只数单边翻转",
    ),
    (
        "regressed 混进 fixed",
        '        elif b and not a:\n            out["regressed"] += 1      # 原本对、现在坏：优先级最高的报警',
        '        elif b and not a:\n            out["fixed"] += 1',
        "regressed 单独计数",
    ),
    (
        "四态只记两态（漏掉 still_broken）",
        '            out["still_broken"] += 1   # 还没轮到它，不算退步',
        "            pass",
        "四态之和等于 case 数",
    ),
]


def main() -> int:
    return self_test(
        page="stage-p2.html", card="p2-16", lab=LAB, build=build, combine=[0, 1],
        mutations=MUTATIONS,
    )


if __name__ == "__main__":
    sys.exit(main())
