"""每个 lab 的 tools/ 下那两个脚本，其实只是同一段样板：

    抽代码 → 铺临时目录 → 跑 harness/run_checks.py → 看退出码

26 个 lab 各抄一遍，必然漂（有的打印 sha、有的不打印，有的 --target 传错）。
所以抽到这里，每个 lab 的 verify_reference.py / self_test.py 各剩 15 行。

用法：

    from refkit import verify_reference, self_test

    def build(tmp: Path, code: str) -> None:      # 铺夹具：把 code 写成被判对象的源码
        (tmp / "agentlab").mkdir()
        (tmp / "agentlab" / "tools.py").write_text(code, encoding="utf-8")

    def main() -> int:
        return verify_reference(page="stage-p1.html", card="p1-9", lab=Path(__file__).parent.parent,
                                build=build)

`build` 只负责铺文件，不负责跑；跑由 refkit 起子进程，这样被判对象崩了也不会带崩判分器。
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Sequence

from htmlcode import block, blocks as _blocks, sha
from mutate import Mutation, run_mutations

Build = Callable[[Path, str], None]


def _baseline(page: str, card: str, idx: int, combine: Sequence[int] | None) -> str:
    """取参考实现原文。combine 给定时把多个代码块按顺序拼起来（有的卡是两个文件）。"""
    if not combine:
        return block(page, card, idx)
    allb = _blocks(page, card)
    return "\n\n".join(allb[i] for i in combine)


def _run(lab: Path, target: Path) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, str(lab / "harness" / "run_checks.py"), "--target", str(target)],
        capture_output=True, text=True, cwd=str(target),
    )
    return r.returncode, r.stdout + r.stderr


def verify_reference(
    *,
    page: str,
    card: str,
    lab: Path,
    build: Build,
    idx: int = 0,
    combine: Sequence[int] | None = None,
    expect_red: Sequence[str] = (),
) -> int:
    """把手册里的参考实现抽出来，跑同一套判分。

    参考实现不存副本：手册改了这里立刻跟着变，红了就是手册和 CONTRACT 对不上。

    expect_red：参考实现**自己没达到** CONTRACT 的检查名。不是放水——是把
    「手册这段代码有问题」显式标出来，修好后这里会提示删掉对应条目。
    """
    code = _baseline(page, card, idx, combine)
    with tempfile.TemporaryDirectory(prefix=f"{card}-ref-") as tmp:
        root = Path(tmp)
        build(root, code)
        label = f"{len(combine)} 个代码块合并" if combine else f"第 {idx + 1} 块"
        print(f"从手册抽取参考实现：{card} {label}  "
              f"{code.count(chr(10)) + 1} 行  sha256 {sha(code)}")
        print("\n用同一套判分检查它：\n")
        rc, out = _run(lab, root)
    print(out.rstrip())

    red = [ln.strip() for ln in out.splitlines()
           if ("FAIL" in ln or "ERR " in ln) and ln.strip()[:2].strip().isdigit()]
    got = [n for n in expect_red if any(n in ln for ln in red)]
    extra = [ln for ln in red if not any(n in ln for n in expect_red)]

    if expect_red:
        print()
        print(f"已知偏差：{len(expect_red)} 条，命中 {len(got)} 条")
        for n in expect_red:
            mark = "命中" if n in got else "未命中 ← 手册可能已修好，删掉这条"
            print(f"  [{mark}] {n}")
        if extra:
            print()
            print("除了已知偏差还有意外红：")
            for ln in extra:
                print(f"  {ln}")
            return 1
        return 0

    return 0 if rc == 0 else 1


def self_test(
    *,
    page: str,
    card: str,
    lab: Path,
    build: Build,
    mutations: Sequence[Mutation],
    idx: int = 0,
    combine: Sequence[int] | None = None,
) -> int:
    """判分器体检：把已知 bug 塞回去，对应断言必须变红。"""

    def run_checks(target: Path) -> tuple[int, str]:
        return _run(lab, target)

    return run_mutations(
        f"{card.upper()} 判分器体检：塞 bug → 判分必须红",
        baseline=_baseline(page, card, idx, combine),
        mutations=mutations,
        build=build,
        run_checks=run_checks,
    )
