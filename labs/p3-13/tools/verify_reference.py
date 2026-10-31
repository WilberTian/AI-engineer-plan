"""证明「参考实现能过判分」。代码从 stage-p3.html 现抽。

    python3 labs/p3-13/tools/verify_reference.py

夹具同时铺 `logs/runs.jsonl`（9 条，来自 harness/logs_fixture.py）。
产出的 `evals/v2.jsonl` 由判分器生成在临时目录里，不进仓库。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from refkit import verify_reference  # noqa: E402


def build(tmp: Path, code: str) -> None:
    """只铺脚本。日志夹具由 harness/logs_fixture.py 提供，判分器自己带进沙箱。"""
    (tmp / "evals").mkdir()
    (tmp / "evals" / "mine_failures.py").write_text(code, encoding="utf-8")


def main() -> int:
    return verify_reference(page="stage-p3.html", card="p3-13", lab=LAB, build=build, idx=1)


if __name__ == "__main__":
    sys.exit(main())
