"""P1-12 判分：10 条测试集本身站不站得住。

被判对象 `evals/v1.jsonl`。这里判的不是「你跑得多少分」（那是 P1-13），
而是「这份测试集能不能区分好坏」——全是能通过用例的测试集，
交上去的报告一定是绿的，但它什么都没证明。

    python3 labs/p1-12/harness/run_checks.py --target ~/code/agentlab-project
"""
from __future__ import annotations

import json
import re
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "_shared"))
from checkkit import exit_missing, run_all  # noqa: E402

COUNT = 10
TOOLS = {"search_notes", "read_file", "fetch_url"}
EXPECT_KEYS = {"tools", "must_contain", "must_not_contain", "max_tool_calls"}
GROUPS = {"happy", "edge", "should_fail"}


class Ctx:
    def __init__(self, target: Path):
        self.path = target / "evals" / "v1.jsonl"
        self.lines = self.path.read_text(encoding="utf-8").splitlines()
        self.rows: list[dict] = []
        self.parse_err: list[tuple[int, str]] = []
        for i, line in enumerate(self.lines, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                self.parse_err.append((i, str(exc)))
                continue
            if isinstance(row, dict):
                self.rows.append(row)
            else:
                self.parse_err.append((i, f"顶层是 {type(row).__name__}"))

    def tags(self, r: dict) -> list[str]:
        t = r.get("tags")
        return t if isinstance(t, list) else []

    def group(self, r: dict) -> str:
        for g in GROUPS:
            if g in self.tags(r):
                return g
        return ""

    def of(self, group: str) -> list[dict]:
        return [r for r in self.rows if self.group(r) == group]

    def expect(self, r: dict) -> dict:
        e = r.get("expect")
        return e if isinstance(e, dict) else {}


# ---------- 文件层 ----------
def c1_parse(ctx: Ctx) -> str:
    assert not ctx.parse_err, (
        "有行不是合法 JSON：" + "; ".join(f"第 {i} 行 {m[:70]}" for i, m in ctx.parse_err[:3])
    )
    return f"{len(ctx.rows)} 行全部可解析"


def c2_count(ctx: Ctx) -> str:
    assert len(ctx.rows) == COUNT, (
        f"实际 {len(ctx.rows)} 条，卡里要求 {COUNT} 条。"
        "少于 10 条时一次翻转就占 10% 以上，你分不清「改好了」和「运气好」"
    )
    return f"{COUNT} 条"


def c3_no_blank(ctx: Ctx) -> str:
    blank = [i for i, ln in enumerate(ctx.lines, 1) if not ln.strip()]
    assert not blank, f"第 {blank[:5]} 行是空行"
    return "无空行"


# ---------- 字段层 ----------
def c4_ids(ctx: Ctx) -> str:
    ids = [r.get("id") for r in ctx.rows]
    dup = {i for i in ids if ids.count(i) > 1}
    assert not dup, f"id 重复：{sorted(dup)[:5]}"
    bad = [str(i) for i in ids if not re.fullmatch(r"t\d{2,3}", str(i))]
    assert not bad, f"id 不合 tNN 格式：{bad[:5]}"
    return f"{len(set(ids))} 个 id 唯一"


def c5_fields(ctx: Ctx) -> str:
    for r in ctx.rows:
        lack = [k for k in ("input", "expect", "tags") if k not in r]
        assert not lack, f"{r.get('id')} 缺字段 {lack}"
        assert isinstance(r["expect"], dict), f"{r.get('id')} 的 expect 不是对象"
        assert isinstance(r["tags"], list) and r["tags"], f"{r.get('id')} 的 tags 是空列表"
    return "input / expect / tags 齐全"


def c6_expect_keys(ctx: Ctx) -> str:
    for r in ctx.rows:
        extra = set(ctx.expect(r)) - EXPECT_KEYS
        assert not extra, (
            f"{r.get('id')} 的 expect 里有判分器不认识的键 {sorted(extra)}——"
            f"只有 {sorted(EXPECT_KEYS)} 会被执行，多写的等于没写"
        )
    return "expect 只用四个键"


# ---------- 分组层 ----------
def c7_three_groups(ctx: Ctx) -> str:
    lack = [g for g in GROUPS if not ctx.of(g)]
    assert not lack, (
        f"缺分组 {lack}。空的那一组不会报错，只是报告里少一行——"
        "而「少了哪一行」正是最该看见的东西"
    )
    return "happy / edge / should_fail 都有"


def c8_should_fail_count(ctx: Ctx) -> str:
    n = len(ctx.of("should_fail"))
    assert n >= 3, (
        f"should_fail 只有 {n} 条，卡里要求至少 3 条。"
        "全是能通过的用例 = 虚假的安全感：它保证你现在的实现能过，不保证它是对的"
    )
    return f"{n} 条应该失败"


def c9_should_fail_kinds(ctx: Ctx) -> str:
    kinds = {t for r in ctx.of("should_fail") for t in ctx.tags(r)}
    for need, why in [
        ("injection", "注入要测「文档/用户让模型忽略指令」时会不会被带走"),
        ("out_of_scope", "越界要测「这系统本来就不该做的事」，否则拒答率没有意义"),
    ]:
        assert need in kinds, (
            f"should_fail 里没有 {need}——{why}。"
            f"现在只有 {sorted(kinds)}"
        )
    return "注入与越界都覆盖了"


# ---------- 可判性 ----------
def c10_no_tool_case(ctx: Ctx) -> str:
    ok = [r for r in ctx.of("happy") if ctx.expect(r).get("tools") == []]
    assert ok, (
        "没有「不该调工具」的 happy 用例。"
        "如果所有用例都要调工具，你就测不出「能直接回答却去查了一堆」这种浪费——"
        "那是线上最常见的坏行为"
    )
    return f"{len(ok)} 条纯回答用例"


def c11_negative_assertion(ctx: Ctx) -> str:
    ok = [r for r in ctx.rows if ctx.expect(r).get("must_not_contain")]
    assert ok, (
        "没有任何 must_not_contain。正向断言只能证明「说了对的」，"
        "管不住「顺带说了错的」——把 system prompt 吐出来、编一个来源，都靠负向断言抓"
    )
    return f"{len(ok)} 条带负向断言"


def c12_edge_is_checkable(ctx: Ctx) -> str:
    """edge 用例必须有 must_contain，光有 tools 不够。

    `tools: ["read_file"]` 只证明「调了」，不证明「处理了」——
    agent 读完报错崩掉、或者返回「好的我读了」，两种都满足 tools 断言。
    要区分「承认失败」和「糊过去」，只能在答案里挑一个词。
    """
    for r in ctx.of("edge"):
        e = ctx.expect(r)
        assert e.get("must_contain"), (
            f"{r.get('id')} 是 edge 用例但没有 must_contain（现在 expect={e}）——"
            "只断言 tools 的话，崩溃、空串、敷衍一句「好的我读了」都能通过，这条测不出错误恢复"
        )
    return f"{len(ctx.of('edge'))} 条 edge 都要求答案里有失败信号"


def c13_no_contradiction(ctx: Ctx) -> str:
    for r in ctx.rows:
        e = ctx.expect(r)
        both = set(e.get("must_contain") or []) & set(e.get("must_not_contain") or [])
        assert not both, (
            f"{r.get('id')} 同一个词 {sorted(both)} 既要求出现又要求不出现——"
            "这条永远红，而你多半会以为是实现的问题"
        )
        bad = set(e.get("tools") or []) - TOOLS
        assert not bad, (
            f"{r.get('id')} 期望调不存在的工具 {sorted(bad)}；"
            f"P1-9 的注册表里只有 {sorted(TOOLS)}"
        )
    return "断言不矛盾，工具名都对得上"


CHECKS = [
    ("每行可解析", c1_parse),
    ("正好 10 条", c2_count),
    ("没有空行", c3_no_blank),
    ("id 唯一且格式统一", c4_ids),
    ("三个字段齐全", c5_fields),
    ("expect 只用四个键", c6_expect_keys),
    ("三类 tag 都有", c7_three_groups),
    ("至少 3 条应该失败", c8_should_fail_count),
    ("注入与越界都覆盖", c9_should_fail_kinds),
    ("有一条不该调工具的用例", c10_no_tool_case),
    ("有负向断言", c11_negative_assertion),
    ("edge 要求答案里有失败信号", c12_edge_is_checkable),
    ("断言不矛盾", c13_no_contradiction),
]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="判 P1-12 的 10 条测试集")
    ap.add_argument("--target", default=".", help="项目根目录（含 evals/）")
    args, rest = ap.parse_known_args()

    target = Path(args.target).expanduser().resolve()
    path = target / "evals" / "v1.jsonl"
    if not path.is_file():
        return exit_missing(
            f"× 在 {target} 下没找到 evals/v1.jsonl",
            "  用 --target 指到项目根目录",
            "  CONTRACT §1 要求 10 行 JSONL 落在这里",
        )
    try:
        ctx = Ctx(target)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return exit_missing(f"× 读文件失败：{type(exc).__name__}: {exc}")

    return run_all(
        "P1-12 判分 · 10 条测试集",
        CHECKS,
        ctx,
        argv=rest,
        subtitle=f"目标 {path}",
        footer=(
            "注意：这里不判通过率——那要真跑模型（P1-13）。\n"
            "      这里只判「这份测试集能不能区分好坏」。全绿的测试集是最贵的那种幻觉。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
