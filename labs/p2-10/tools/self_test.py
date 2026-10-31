"""判分器体检：往 answer.py 里塞已知的拒答错法。

    python3 labs/p2-10/tools/self_test.py
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
        "去掉第一层（硬门槛形同虚设）",
        "    if not chunks or top_score < 0.35:      # 阈值要靠 W09 的 unanswerable 集来定",
        "    if False:      # 阈值要靠 W09 的 unanswerable 集来定",
        "空 chunks 直接拒答且不调模型",
    ),
    (
        "阈值写成 <= 0.35（边界多拒一档）",
        "    if not chunks or top_score < 0.35:",
        "    if not chunks or top_score <= 0.35:",
        "边界 0.35 放行",
    ),
    (
        "阈值降到 0.05（几乎不拦）",
        "    if not chunks or top_score < 0.35:",
        "    if not chunks or top_score < 0.05:",
        "0.34 被拦住",
    ),
    (
        "只认「资料中没有」，漏掉「无法回答」",
        '    if "资料中没有" in raw or "无法回答" in raw:',
        '    if "资料中没有" in raw:',
        "另一个拒答说法也认",
    ),
    (
        "模型拒答时返回原文而不是 REFUSE",
        '        return REFUSE, "refused_by_model"',
        '        return raw, "refused_by_model"',
        "两句拒答文案一致",
    ),
    (
        "两种拒答用同一个原因",
        '        return REFUSE, "refused_by_model"',
        '        return REFUSE, "refused_low_score"',
        "两种拒答原因可区分",
    ),
    (
        "调模型时不给 system 段（第二层没有出口）",
        '        {"role": "system", "content": SYSTEM_WITH_REFUSE_RULE},',
        '        {"role": "user", "content": SYSTEM_WITH_REFUSE_RULE},',
        "模型看到拒答规则",
    ),
    (
        "正常回答也被当成拒答",
        '    if "资料中没有" in raw or "无法回答" in raw:',
        '    if "资料中没有" in raw or "无法回答" in raw or raw:',
        "正常回答原样返回",
    ),
]


def main() -> int:
    return self_test(page="stage-p2.html", card="p2-10", lab=LAB, build=build, mutations=MUTATIONS)


if __name__ == "__main__":
    sys.exit(main())
