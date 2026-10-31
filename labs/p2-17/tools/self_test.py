"""判分器体检：往 memory.py 里塞已知错。

    python3 labs/p2-17/tools/self_test.py
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
        "冲突时并存而不是覆盖",
        "    store[m.key] = m            # 后写的覆盖先写的：用户改主意了",
        '    store[m.key + ":" + m.source] = m',
        "冲突后只有一条且是新值",
    ),
    (
        "同值重写也当成 updated",
        '    if old.value == m.value:\n        return "noop"           # 重复写入不制造噪音',
        "    if False:\n        return \"noop\"",
        "同值重写返回 noop",
    ),
    (
        "save 不写文件（只在内存里）",
        "    path.write_text(",
        "    (lambda *a, **k: None)(",
        "跨进程能读到（真落盘）",
    ),
    (
        "load 遇到不存在的文件抛异常",
        "    if not path.exists():\n        return {}",
        "    if False:\n        return {}",
        "文件不存在返回空库",
    ),
    (
        "recall 不按 k 截断",
        '    return "\\n".join(f"- {m.value}" for m in hits[:k])',
        '    return "\\n".join(f"- {m.value}" for m in hits)',
        "按 k 限制注入条数",
    ),
    (
        "偏好不优先",
        '    hits.sort(key=lambda m: m.kind != "preference")   # 偏好排在一般事实前面',
        "    pass",
        "偏好排在一般事实前",
    ),
]


def main() -> int:
    return self_test(
        page="stage-p2.html", card="p2-17", lab=LAB, build=build, mutations=MUTATIONS,
    )


if __name__ == "__main__":
    sys.exit(main())
