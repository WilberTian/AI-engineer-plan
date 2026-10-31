"""证明「参考实现能过判分」。代码从 stage-p4.html 现抽。

    python3 labs/p4-8/tools/verify_reference.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from refkit import verify_reference  # noqa: E402


def build(tmp: Path, code: str) -> None:
    pkg = tmp / "agentlab"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "cost.py").write_text(code, encoding="utf-8")


def main() -> int:
    return verify_reference(page="stage-p4.html", card="p4-8", lab=LAB, build=build)


if __name__ == "__main__":
    sys.exit(main())
