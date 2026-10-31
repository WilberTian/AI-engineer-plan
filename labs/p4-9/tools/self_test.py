"""判分器体检：往 routing.py 里塞已知分类错。

    python3 labs/p4-9/tools/self_test.py
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
        "难度标记被删掉（只靠长度和默认档）",
        '    hard_markers = ("分析", "对比", "为什么", "设计", "重构", "debug", "证明")',
        "    hard_markers = ()",
        "七个难度标记都升到 hard",
    ),
    (
        "simple 不再检查 has_tools",
        "    if len(task) < 40 and not has_tools and history_len == 0:",
        "    if len(task) < 40 and history_len == 0:",
        "带工具不判 simple",
    ),
    (
        "simple 不再检查 history_len",
        "    if len(task) < 40 and not has_tools and history_len == 0:",
        "    if len(task) < 40 and not has_tools:",
        "有历史不判 simple",
    ),
    (
        "历史边界写成 >=10（10 轮就升级）",
        "or history_len > 10:",
        "or history_len >= 10:",
        "历史边界落在 10/11 之间",
    ),
    (
        "长度阈值改成 400（几乎全是 simple）",
        "    if len(task) < 40 and not has_tools and history_len == 0:",
        "    if len(task) < 400 and not has_tools and history_len == 0:",
        "长度阈值真的起作用",
    ),
    (
        "三档都用同一个模型",
        '        return Route("hard", "gpt-4.1", "需要推理/长上下文 → 大模型")',
        '        return Route("hard", "gpt-4.1-mini", "需要推理/长上下文 → 大模型")',
        "三档至少用两个模型",
    ),
]


def main() -> int:
    return self_test(
        page="stage-p4.html", card="p4-9", lab=LAB, build=build, mutations=MUTATIONS,
    )


if __name__ == "__main__":
    sys.exit(main())
