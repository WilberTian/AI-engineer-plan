"""证明「参考实现能过判分」——代码从手册 HTML 里现抽，不在仓库里存第二份。

    python3 labs/p1-2/tools/verify_reference.py          # 用当前解释器（需有 pydantic）
    uv run python labs/p1-2/tools/verify_reference.py

有一条特例：手册当前版本在两条上**确实不达标**（见 NOTES §4）。
所以这里不要求「全绿」，而要求「失败的恰好是已知那两条」——
多一条或少一条都算手册改动带来的真问题，退出码非 0。
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from htmlcode import REPO, block, sha  # noqa: E402

RUN_CHECKS = LAB / "harness" / "run_checks.py"
CARD, IDX = "p1-2", 0

# 手册 p1-2 参考实现的已知偏差。修好之后这里应该清空。
KNOWN_DEVIATIONS = {
    "citations 不传也受同一规则约束",   # field_validator 不校默认值 → 规则整条失效
    "refused=True 时无引用应通过",      # info.data 里没有 refused（字段顺序）→ 误杀合法数据
}

RED_LINE = re.compile(r"^\s*\d+\s+(FAIL|ERR)\s+(.+?)(?:\s{3,}.*)?$", re.M)


def main() -> int:
    if not (REPO / "stage-p1.html").is_file():
        raise SystemExit(f"× 找不到 {REPO / 'stage-p1.html'}")

    code = block("stage-p1.html", CARD, IDX)
    with tempfile.TemporaryDirectory(prefix="p1-2-ref-") as tmp:
        pkg = Path(tmp) / "agentlab"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "schema.py").write_text(code, encoding="utf-8")
        print(f"从手册抽取参考实现：schema.py ← {CARD} 第 {IDX + 1} 块  "
              f"{code.count(chr(10)) + 1} 行  sha256 {sha(code)}")
        print("\n用同一套判分检查它：")
        r = subprocess.run(
            [sys.executable, str(RUN_CHECKS), "--target", str(tmp)],
            capture_output=True, text=True,
        )

    out = r.stdout + r.stderr
    print(out)
    if r.returncode == 2:                      # 环境问题（没装 pydantic 等），原样传出
        return 2

    failed = {m.group(2).strip() for m in RED_LINE.finditer(out) if m.group(2).strip()}
    unknown = failed - KNOWN_DEVIATIONS
    fixed = KNOWN_DEVIATIONS - failed

    print("-" * 74)
    if not unknown and not fixed:
        print(f"结果符合预期：失败的恰好是 NOTES §4 记录的 {len(KNOWN_DEVIATIONS)} 条已知偏差。")
        print("这两个洞是故意留着的——它们正是这张卡要你自己想清楚的地方。")
        return 0
    if unknown:
        print(f"× 出现未记录的失败：{sorted(unknown)}")
        print("  手册改过、或判分规则本身有问题，去核对再更新 NOTES。")
    if fixed:
        print(f"! 已知偏差里这些不再失败了：{sorted(fixed)}")
        print("  说明手册已修好 → 把它们从 KNOWN_DEVIATIONS 删掉，并把 NOTES §4 改成「已修」。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
