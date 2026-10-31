"""判分器自己的体检：往 run_eval.py 里塞已知 bug，看判分能不能抓住。

    python3 labs/p1-13/tools/self_test.py

6 个 mutation 分两层打：前四个打 judge()，后两个打 end-to-end。
只测 judge 会漏掉 runner 本身（输出文件、退出码、单条崩溃隔离）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from htmlcode import block                 # noqa: E402
from mutate import run_mutations           # noqa: E402

RUN_CHECKS = LAB / "harness" / "run_checks.py"
CARD, IDX = "p1-13", 0

MUTATIONS = [
    (
        "judge 不检查终止状态",
        '    if res.status not in ("done",):\n        return False, f"未正常结束: {res.status}"',
        "    if False:\n        return False, \"\"",
        "judge：status 非 done 判红",
    ),
    (
        "judge 不检查工具选择",
        '    for t in expect.get("tools", []):',
        "    for t in []:",
        "judge：该调的工具没调判红",
    ),
    (
        "judge 忽略 must_not_contain",
        '    for kw in expect.get("must_not_contain", []):',
        "    for kw in []:",
        "judge：must_not_contain 出现判红",
    ),
    (
        "关键词区分大小写",
        "    low = answer.lower()",
        "    low = answer",
        "judge：关键词大小写不敏感",
    ),
    (
        "单条崩掉就中断整轮",
        "        except Exception as exc:  # noqa: BLE001",
        "        except ZeroDivisionError as exc:",
        "端到端：单条崩掉不中断整轮",
    ),
    (
        "退出码永远 0",
        "    return 0 if npass == n else 1",
        "    return 0",
        "端到端：有失败时退出码非 0",
    ),
]


def build(tmp: Path, script_src: str) -> None:
    evals = tmp / "evals"
    evals.mkdir()
    (evals / "run_eval.py").write_text(script_src, encoding="utf-8")


def run_checks(target: Path) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, str(RUN_CHECKS), "--script", str(target / "evals" / "run_eval.py")],
        capture_output=True, text=True,
    )
    return r.returncode, r.stdout + r.stderr


def main() -> int:
    return run_mutations(
        "P1-13 判分器体检：塞 bug → 判分必须红",
        baseline=block("stage-p1.html", CARD, IDX),
        mutations=MUTATIONS,
        build=build,
        run_checks=run_checks,
    )


if __name__ == "__main__":
    sys.exit(main())
