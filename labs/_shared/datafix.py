"""数据类 lab 的两个薄壳：判 JSONL / JSON 文件的那些。

判代码的 lab 用 `refkit`：从手册抽参考实现 → 跑同一套判分。
判数据的 lab 没有参考实现可抽——手册只给一行格式样例，30 条测试集是读者自己写的。
所以换一种证法：

- `verify_ok`  造一个**最小合规夹具**，14 条必须全绿 → 证明判据不是恒假的
- `self_test`  把夹具弄坏一处，对应那条必须变红 → 证明判据真的在看那一处

为什么先要「能被满足」这一步：一个怎么都过不了的判分器比没有更糟。
读者会以为是自己写错了，然后照着判据去改一份本来合规的数据。

夹具内容从 `CONTRACT.md` 的分布表派生，不引用手册里的样例数据——
样例是格式说明，照抄它等于测试集里放了个空壳。
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Sequence

# 夹具是「相对路径 → 文本内容」的整份文件树
Tree = dict[str, str]
# (名字, 弄坏它的函数, 期望报出来的检查名)
DataMutation = tuple[str, Callable[[Tree], Tree], str]


def _run(lab: Path, root: Path) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, str(lab / "harness" / "run_checks.py"), "--target", str(root)],
        capture_output=True, text=True, cwd=str(root),
    )
    return r.returncode, r.stdout + r.stderr


def _materialize(root: Path, tree: Tree) -> None:
    for rel, text in tree.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def _caught(output: str, expect: str) -> bool:
    return any(
        ("FAIL" in line or "ERR " in line) and expect in line
        for line in output.splitlines()
    )


def verify_ok(*, lab: Path, tree: Tree) -> int:
    """合规夹具跑一遍，必须全绿。"""
    print("=" * 74)
    print("最小合规夹具：按 CONTRACT 的分布造一份，全部检查必须绿")
    print("=" * 74)
    for rel, text in tree.items():
        print(f"  {rel}  {text.count(chr(10)) + 1} 行")
    print()

    with tempfile.TemporaryDirectory(prefix="lab-fx-") as tmp:
        root = Path(tmp)
        _materialize(root, tree)
        rc, out = _run(lab, root)
    print(out.rstrip())

    ok = rc == 0
    print()
    if ok:
        print("夹具全绿 → 判据是可满足的（不是怎么都过不了）")
    else:
        print("× 合规夹具竟然没全绿：说明判据本身自相矛盾，或者夹具漏了字段。")
        print("  这一条比 self_test 更优先——先让合规的能过，再谈抓不抓得住坏数据。")
    return 0 if ok else 1


def self_test(*, lab: Path, tree: Tree, mutations: Sequence[DataMutation]) -> int:
    """把合规夹具弄坏一处，对应的检查必须变红。"""
    print("=" * 74)
    print("判分器体检：弄坏夹具 → 判分必须红")
    print("=" * 74)

    npass = nfail = 0
    for name, breakit, expect in mutations:
        broken = breakit({k: v for k, v in tree.items()})
        with tempfile.TemporaryDirectory(prefix="lab-dmut-") as tmp:
            root = Path(tmp)
            _materialize(root, broken)
            rc, out = _run(lab, root)

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
