"""证明「参考实现能过判分」——代码从手册 HTML 里现抽，不在仓库里存第二份。

    python3 labs/p1-13/tools/verify_reference.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from htmlcode import REPO, block, sha  # noqa: E402

RUN_CHECKS = LAB / "harness" / "run_checks.py"
CARD, IDX = "p1-13", 0


def main() -> int:
    if not (REPO / "stage-p1.html").is_file():
        raise SystemExit(f"× 找不到 {REPO / 'stage-p1.html'}")

    code = block("stage-p1.html", CARD, IDX)
    with tempfile.TemporaryDirectory(prefix="p1-13-ref-") as tmp:
        evals = Path(tmp) / "evals"
        evals.mkdir()
        script = evals / "run_eval.py"
        script.write_text(code, encoding="utf-8")
        print(f"从手册抽取参考实现：evals/run_eval.py ← {CARD} 第 {IDX + 1} 块  "
              f"{code.count(chr(10)) + 1} 行  sha256 {sha(code)}")
        print("\n用同一套判分检查它：")
        r = subprocess.run(
            [sys.executable, str(RUN_CHECKS), "--script", str(script)], text=True,
        )
        return r.returncode


if __name__ == "__main__":
    sys.exit(main())
