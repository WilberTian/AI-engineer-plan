"""证明「参考实现能过判分」。两个代码块分别落到两个文件。

    python3 labs/p5-14/tools/verify_reference.py

这块卡不是一个文件，所以不走 refkit 的单一 code 参数：
第 1 块 → agentlab/flags.py，第 2 块 → scripts/ablate.py。

参考实现有两条不达标：
  1. `on = run_eval(flags=BASE)` 写在循环里 —— 基线算了 4 次
  2. `self_check` 默认就是 False，「关掉它」等于没改 —— 这次对比 delta 恒为 0
见 NOTES §2。
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from htmlcode import block, sha  # noqa: E402

PAGE, CARD = "stage-p5.html", "p5-14"
KNOWN_RED = ["每个特性都真的被改过", "基线只算一次"]


def build(root: Path, flags_code: str, ablate_code: str) -> None:
    (root / "agentlab").mkdir()
    (root / "scripts").mkdir()
    (root / "agentlab" / "__init__.py").write_text("", encoding="utf-8")
    (root / "agentlab" / "flags.py").write_text(flags_code, encoding="utf-8")
    (root / "scripts" / "ablate.py").write_text(ablate_code, encoding="utf-8")


# self_test 用：只换一个文件，另一个用手册原样
def build_flags_only(tmp: Path, code: str) -> None:
    build(tmp, code, block(PAGE, CARD, 1))


def build_ablate_only(tmp: Path, code: str) -> None:
    build(tmp, block(PAGE, CARD, 0), code)


def main() -> int:
    flags_code = block(PAGE, CARD, 0)
    ablate_code = block(PAGE, CARD, 1)
    print(f"从手册抽取参考实现：{CARD} 第 1 块 → agentlab/flags.py  "
          f"{flags_code.count(chr(10)) + 1} 行  sha256 {sha(flags_code)}")
    print(f"                         第 2 块 → scripts/ablate.py  "
          f"{ablate_code.count(chr(10)) + 1} 行  sha256 {sha(ablate_code)}")
    print("\n用同一套判分检查它：\n")

    with tempfile.TemporaryDirectory(prefix=f"{CARD}-ref-") as tmp:
        root = Path(tmp)
        build(root, flags_code, ablate_code)
        r = subprocess.run(
            [sys.executable, str(LAB / "harness" / "run_checks.py"), "--target", str(root)],
            capture_output=True, text=True, cwd=str(root),
        )
        out = r.stdout + r.stderr
    print(out.rstrip())

    red = [ln.strip() for ln in out.splitlines()
           if ("FAIL" in ln or "ERR " in ln) and ln.strip()[:2].strip().isdigit()]
    got = [n for n in KNOWN_RED if any(n in ln for ln in red)]
    extra = [ln for ln in red if not any(n in ln for n in KNOWN_RED)]

    print()
    print(f"已知偏差：{len(KNOWN_RED)} 条，命中 {len(got)} 条")
    for n in KNOWN_RED:
        mark = "命中" if n in got else "未命中 ← 手册可能已修好，删掉这条"
        print(f"  [{mark}] {n}")
    if extra:
        print()
        print("除了已知偏差还有意外红：")
        for ln in extra:
            print(f"  {ln}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
