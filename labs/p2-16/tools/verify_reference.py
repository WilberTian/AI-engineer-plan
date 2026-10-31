"""证明「参考实现能过判分」。代码从 stage-p2.html 现抽。

    python3 labs/p2-16/tools/verify_reference.py

注意：两个代码块要合并成一个 evals/metrics.py（手册分两段讲同一文件）。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from refkit import verify_reference  # noqa: E402


def build(tmp: Path, code: str) -> None:
    (tmp / "evals").mkdir()
    (tmp / "evals" / "metrics.py").write_text(code, encoding="utf-8")


def main() -> int:
    return verify_reference(
        page="stage-p2.html", card="p2-16", lab=LAB, build=build, combine=[0, 1],
    )


if __name__ == "__main__":
    sys.exit(main())
