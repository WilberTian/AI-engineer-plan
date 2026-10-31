"""判分器体检：往被判对象里塞已知 bug，看判分能不能抓住。

一个「永远通过」的判分器等于没有判分器。所以每个 lab 都要证明：
把某个真实踩过的坑重新塞回去，对应的那条断言必须变红。

这也是手册 P1-12 的原则：eval 里必须有「应该失败」的 case。

每个 mutation 是 (名字, 原文, 改坏成什么, 期望报出来的检查名)。
期望写具体的检查名，不写「随便哪条红就行」——后者在整份文件崩掉时也会通过，证明不了任何事。
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable, Sequence

Mutation = tuple[str, str, str, str]


def patch(text: str, pairs: Sequence[tuple[str, str]]) -> str:
    """按顺序做文本替换；找不到原文就抛错（原文找不到 = patch 失效，不能静默跳过）。"""
    for old, new in pairs:
        if old not in text:
            raise LookupError(f"patch 原文没找到：{old[:60]!r}")
        text = text.replace(old, new, 1)
    return text


def _caught(output: str, expect: str) -> bool:
    return any(
        ("FAIL" in line or "ERR " in line) and expect in line
        for line in output.splitlines()
    )


def run_mutations(
    title: str,
    *,
    baseline: str,
    mutations: Sequence[Mutation],
    build: Callable[[Path, str], None],
    run_checks: Callable[[Path], tuple[int, str]],
) -> int:
    """build(tmp, 源码文本) 负责铺夹具；run_checks(tmp) 返回 (退出码, 输出)。"""
    print("=" * 74)
    print(title)
    print("=" * 74)

    npass = nfail = 0
    for name, old, new, expect in mutations:
        if old not in baseline:
            nfail += 1
            print(f"  FAIL  {name}")
            print("        原文没找到，mutation 失效（手册代码可能已改）")
            continue

        with tempfile.TemporaryDirectory(prefix="lab-mut-") as tmp:
            build(Path(tmp), baseline.replace(old, new, 1))
            rc, out = run_checks(Path(tmp))

        if rc != 0 and _caught(out, expect):
            npass += 1
            print(f"  PASS  {name}")
            print(f"        被「{expect}」抓住")
        else:
            nfail += 1
            print(f"  FAIL  {name}")
            print(f"        期望「{expect}」报错，但 exit={rc} 且那条检查没红")
            for line in out.splitlines():
                if "PASS" in line or "FAIL" in line or "ERR" in line:
                    print(f"        | {line.strip()}")

    print("-" * 74)
    print(f"合计 {npass + nfail} 个 mutation：判分抓住 {npass} / 漏掉 {nfail}")
    if nfail:
        print("漏掉的那条断言是摆设，要改。")
    return 0 if nfail == 0 else 1
