"""labs 共用的检查表执行器。

为什么共用：每个 lab 各写一份 print + 计数 + 退出码，格式必然漂，
而「退出码 0 = 全过」是接 CI 的唯一接口，不能各说各话。

约定：
- 每条检查是一个 `fn(ctx) -> str`。返回非空字符串当作「证据」打出来，
  说明「这条为什么过了」——只说 PASS 不说细节，等于没法复核。
- 用 assert 表达失败。AssertionError 的消息必须是**可操作的**：
  说清实际值是什么、期望是什么。
- 其它异常一律记 ERR（不算过），因为它通常意味着被判对象导入失败或崩了。

退出码：0 全过；1 有红；2 前置条件不满足（找不到被判对象）。
"""
from __future__ import annotations

import argparse
import sys
import traceback
from typing import Any, Callable, Sequence

Check = tuple[str, Callable[[Any], str]]


def banner(title: str, subtitle: str = "") -> None:
    print("=" * 74)
    print(title)
    if subtitle:
        print(subtitle)
    print("=" * 74)


def run_all(
    title: str,
    checks: Sequence[Check],
    ctx: Any,
    *,
    footer: str | None = None,
    argv: list[str] | None = None,
    subtitle: str = "",
) -> int:
    """跑完 checks 并打印，返回进程退出码。--filter 只跑名字含某个词的检查。"""
    ap = argparse.ArgumentParser(description=title)
    ap.add_argument("--filter", default="", help="只跑名字里含这个词的检查")
    args = ap.parse_args(argv)

    banner(title, subtitle)
    npass = nfail = 0
    for i, (name, fn) in enumerate(checks, 1):
        if args.filter and args.filter not in name:
            continue
        try:
            detail = fn(ctx)
            npass += 1
            print(f"  {i:2d} PASS  {name}" + (f"   [{detail}]" if detail else ""))
        except AssertionError as exc:
            nfail += 1
            print(f"  {i:2d} FAIL  {name}")
            print(f"          {exc}")
        except Exception as exc:  # noqa: BLE001
            nfail += 1
            print(f"  {i:2d} ERR   {name}   {type(exc).__name__}: {exc}")
            if args.filter:                       # 单跑一条时给完整栈，方便定位
                traceback.print_exc()

    print("-" * 74)
    print(f"合计 {npass + nfail} 条：PASS {npass} / FAIL+ERR {nfail}")
    if footer:
        print()
        print(footer)
    return 0 if nfail == 0 else 1


def exit_missing(*lines: str) -> int:
    """前置条件不满足时的统一出口。"""
    for line in lines:
        print(line)
    return 2
