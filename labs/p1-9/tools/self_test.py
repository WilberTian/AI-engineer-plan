"""判分器自己的体检：往 tools.py 里塞已知 bug，看判分能不能抓住。

    python3 labs/p1-9/tools/self_test.py

6 个 mutation 全部对应真实的越权/静默失败，不是随手改坏的：
「永远通过」的判分器等于没有判分器（手册 P1-12 的原则）。
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
CARD, IDX = "p1-9", 0

MUTATIONS = [
    (
        "重名注册被静默覆盖",
        '        if tool.name in self._tools:\n'
        '            raise ValueError(f"工具重名: {tool.name}")',
        "        if False:\n            pass",
        "重名注册当场报错",
    ),
    (
        "报错时不带同目录候选",
        '        siblings = [str(x) for x in p.parent.glob("*")][:5] if p.parent.exists() else []',
        "        siblings = []",
        "read_file 报错时给同目录候选",
    ),
    (
        "不拦绝对路径",
        "    if p.is_absolute():",
        "    if False:  # mutation",
        "read_file 拒绝绝对路径",
    ),
    (
        "不拦 .. 上跳",
        '    if ".." in p.parts:',
        "    if False:  # mutation",
        "read_file 拒绝 .. 上跳",
    ),
    (
        "spec 里不带 description",
        '                "description": self.description,',
        '                "description": "",',
        "每个工具的 description 够用",
    ),
    (
        "fetch_url 不校验协议",
        '    if not url.startswith(("http://", "https://")):',
        "    if False:  # mutation",
        "fetch_url 只接受 http/https",
    ),
]


def build(tmp: Path, tools_src: str) -> None:
    pkg = tmp / "agentlab"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "tools.py").write_text(tools_src, encoding="utf-8")


def run_checks(target: Path) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, str(RUN_CHECKS), "--target", str(target)],
        capture_output=True, text=True,
    )
    return r.returncode, r.stdout + r.stderr


def main() -> int:
    return run_mutations(
        "P1-9 判分器体检：塞 bug → 判分必须红",
        baseline=block("stage-p1.html", CARD, IDX),
        mutations=MUTATIONS,
        build=build,
        run_checks=run_checks,
    )


if __name__ == "__main__":
    sys.exit(main())
