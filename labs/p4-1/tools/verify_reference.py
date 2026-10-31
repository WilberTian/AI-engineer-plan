"""证明「参考实现能过判分」。代码从 stage-p4.html 现抽，不在仓库里存第二份。

    python3 labs/p4-1/tools/verify_reference.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from refkit import verify_reference  # noqa: E402

TOOLS_STUB = '''"""判分夹具：只给 ToolResult，其余不是本卡判分对象。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ToolResult:
    ok: bool
    content: str
'''


def build(tmp: Path, code: str) -> None:
    pkg = tmp / "agentlab"
    (pkg / "resilience").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "tools.py").write_text(TOOLS_STUB, encoding="utf-8")
    (pkg / "resilience" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "resilience" / "faults.py").write_text(code, encoding="utf-8")


def main() -> int:
    return verify_reference(page="stage-p4.html", card="p4-1", lab=LAB, build=build)


if __name__ == "__main__":
    sys.exit(main())
