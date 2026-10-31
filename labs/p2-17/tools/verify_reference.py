"""证明「参考实现能过判分」。代码从 stage-p2.html 现抽。

    python3 labs/p2-17/tools/verify_reference.py

参考实现有一条不达标：`recall` 用 `query.split()` 切查询词，
连续中文切不出词，所以中文查询永远召回空。见 NOTES §2。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from refkit import verify_reference  # noqa: E402

KNOWN_RED = ["中文查询能召回"]


def build(tmp: Path, code: str) -> None:
    pkg = tmp / "agentlab"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "memory.py").write_text(code, encoding="utf-8")


def main() -> int:
    return verify_reference(
        page="stage-p2.html", card="p2-17", lab=LAB, build=build, expect_red=KNOWN_RED,
    )


if __name__ == "__main__":
    sys.exit(main())
