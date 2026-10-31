"""判分器体检：把 prompt 的排布改坏，对应的检查必须变红。

    python3 labs/p3-5/tools/self_test.py

这几个 mutation 都是「代码看起来还正常」的错法——尤其前两个：
把动态段挪到前面，输出照样读得通顺，只有缓存命中率和 p95 会变。
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
        "动态段挪到最前（前缀每轮都变）",
        "    parts = [IDENTITY, BOUNDARIES, TOOL_RULES, OUTPUT, dynamic]",
        "    parts = [dynamic, IDENTITY, BOUNDARIES, TOOL_RULES, OUTPUT]",
        "五段顺序对",
    ),
    (
        "extra 插到动态段之前",
        '        parts.append(f"本次任务补充说明：\\n{extra}")',
        '        parts.insert(4, f"本次任务补充说明：\\n{extra}")',
        "extra 在末尾",
    ),
    (
        "文件数写死 0",
        '    files = len(list(Path("data/corpus").glob("*.md")))',
        "    files = 0",
        "文件数来自目录",
    ),
    (
        "段间只用单换行",
        '    return "\\n\\n".join(p.strip() for p in parts if p.strip())',
        '    return "\\n".join(p.strip() for p in parts if p.strip())',
        "空行分隔且无三连换行",
    ),
    (
        "extra 为空时也拼上标题",
        "    if extra:",
        "    if True:",
        "空 extra 不留标题",
    ),
    (
        "输出要求段改标题（五段缺一）",
        'OUTPUT = """输出要求：',
        'OUTPUT = """格式：',
        "五段齐全",
    ),
    (
        "工具规则删掉次数上限",
        "4. 最多 6 次工具调用，信息足够就立刻给答案",
        "4. 信息足够就立刻给答案",
        "工具规则有次数上限",
    ),
]


def main() -> int:
    return self_test(page="stage-p3.html", card="p3-5", lab=LAB, build=build, mutations=MUTATIONS)


if __name__ == "__main__":
    sys.exit(main())
