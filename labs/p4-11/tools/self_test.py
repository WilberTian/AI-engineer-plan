"""判分器体检：往 latency.py 里塞已知错。

    python3 labs/p4-11/tools/self_test.py
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
        "TTFT 用结束时间算（把生成段也算进去）",
        "        return (self.t_first_token - self.t_start) * 1000 if self.t_first_token else 0",
        "        return (self.t_end - self.t_start) * 1000",
        "ttft 由首 token 时间算出",
    ),
    (
        "非流式时把 TTFT 当成总时长",
        "        return (self.t_first_token - self.t_start) * 1000 if self.t_first_token else 0",
        "        return (self.t_end - self.t_start) * 1000 if self.t_first_token else (self.t_end - self.t_start) * 1000",
        "非流式时 ttft 为 0",
    ),
    (
        "total 只算首 token 之前（漏掉生成段）",
        "        return (self.t_end - self.t_start) * 1000",
        "        return (self.t_first_token - self.t_start) * 1000",
        "total 是全程跨度",
    ),
    (
        "空列表不返回 0 而是抛下标错",
        "    if not values:\n        return 0.0",
        "    if False:\n        return 0.0",
        "空列表 p95 为 0",
    ),
    (
        "分位数改成线性插值",
        "    idx = min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))\n    return s[idx]",
        "    pos = p / 100 * (len(s) - 1)\n    lo = int(pos)\n    hi = min(len(s) - 1, lo + 1)\n    return s[lo] + (s[hi] - s[lo]) * (pos - lo)",
        "p95 用最近邻不插值",
    ),
    (
        "percentile 就地把入参排序",
        "    s = sorted(values)",
        "    s = values\n    s.sort()",
        "percentile 不改入参",
    ),
]


def main() -> int:
    return self_test(
        page="stage-p4.html", card="p4-11", lab=LAB, build=build, mutations=MUTATIONS,
    )


if __name__ == "__main__":
    sys.exit(main())
