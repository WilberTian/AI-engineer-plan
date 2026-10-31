"""证明「参考实现能过判分」。代码从 stage-p4.html 现抽。

    python3 labs/p4-13/tools/verify_reference.py

参考实现有一条不达标：只统计 `kind=="llm"`，检索和重排的 span 被静默丢掉，
而卡里正文明确要求「拆到每一次模型调用、每一次检索、每一次重排」。见 NOTES §2。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from refkit import verify_reference  # noqa: E402

KNOWN_RED = ["检索/重排 span 不被静默丢掉"]


def build(tmp: Path, code: str) -> None:
    (tmp / "scripts").mkdir()
    (tmp / "scripts" / "breakdown.py").write_text(code, encoding="utf-8")


def main() -> int:
    return verify_reference(
        page="stage-p4.html", card="p4-13", lab=LAB, build=build, expect_red=KNOWN_RED,
    )


if __name__ == "__main__":
    sys.exit(main())
