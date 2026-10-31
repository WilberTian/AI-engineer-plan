"""证明「参考实现能过判分」。代码从 stage-p4.html 现抽。

    python3 labs/p4-9/tools/verify_reference.py

参考实现有一条不达标：难度标记判断排在「短问题」之后，于是「设计一个分块策略」
这种短而难的任务被降到小模型。见 NOTES §2。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from refkit import verify_reference  # noqa: E402

KNOWN_RED = ["短但含难度标记仍判 hard"]


def build(tmp: Path, code: str) -> None:
    pkg = tmp / "agentlab"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "routing.py").write_text(code, encoding="utf-8")


def main() -> int:
    return verify_reference(
        page="stage-p4.html", card="p4-9", lab=LAB, build=build, expect_red=KNOWN_RED,
    )


if __name__ == "__main__":
    sys.exit(main())
