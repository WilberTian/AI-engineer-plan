"""证明「参考实现能过判分」。代码从 stage-p3.html 现抽（两个代码块拼成一个文件）。

    python3 labs/p3-12/tools/verify_reference.py

第一块是 `assemble` / `cached_ratio`，第二块是 `STATE_BAR` 模板——
它们是同一个 `context.py` 的两段，所以要拼起来才有 `STATE_BAR`。
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
    (pkg / "context.py").write_text(code, encoding="utf-8")


def main() -> int:
    return verify_reference(
        page="stage-p3.html", card="p3-12", lab=LAB, build=build, combine=[0, 1],
    )


if __name__ == "__main__":
    sys.exit(main())
