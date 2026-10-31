"""判分器体检：往 breakdown.py 里塞已知错。

    python3 labs/p4-13/tools/self_test.py
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
        "不按名字聚合（每次调用单独一行）",
        "        agg = rows[s.name]\n        agg[0] += cost\n        agg[1] += s.ms",
        "        rows[s.name + str(s.ms)][0] += cost\n        rows[s.name + str(s.ms)][1] += s.ms",
        "同名 span 合并成本",
    ),
    (
        "降序改成升序",
        "    out.sort(key=lambda r: -r[1])",
        "    out.sort(key=lambda r: r[1])",
        "按成本降序排列",
    ),
    (
        "成本只算输出 token",
        "        cost = s.in_tok * COST_IN + s.out_tok * COST_OUT",
        "        cost = s.out_tok * COST_OUT",
        "成本 = in×单价 + out×单价",
    ),
    (
        "耗时字段填 0",
        "        agg[1] += s.ms",
        "        agg[1] += 0",
        "同名 span 累加耗时",
    ),
    (
        "总成本为 0 时除零崩",
        "    total_cost = sum(v[0] for v in rows.values()) or 1",
        "    total_cost = sum(v[0] for v in rows.values())",
        "零 token 不崩",
    ),
    (
        "就地对 trace.spans 排序",
        "    for s in trace.spans:",
        "    for s in sorted(trace.spans, key=lambda x: -x.ms): trace.spans.sort(key=lambda x: -x.ms) or None\n    for s in []:",
        "不修改入参",
    ),
]


def main() -> int:
    return self_test(
        page="stage-p4.html", card="p4-13", lab=LAB, build=build, mutations=MUTATIONS,
    )


if __name__ == "__main__":
    sys.exit(main())
