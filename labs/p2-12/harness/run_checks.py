"""P2-12 判分：30 条测试集的分布与字段。

被判对象 `evals/rag_v2.jsonl`。判的是**分布**，不是题目质量——
「这条 gold_answer 抄得对不对」只能人对着语料核。

为什么分布值得判：通过率是一个平均数。五类条数一乱，平均数就会被某一类主导，
于是「整体 0.8」既可能是「事实型很强」也可能是「多跳六条全错被盖住」。

    python3 labs/p2-12/harness/run_checks.py --target ~/code/agentlab-project
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

# 卡里定死的分布。改这里等于改判据，先改 CONTRACT
EXPECT = {"fact": 12, "multi_hop": 6, "precise": 4, "unanswerable": 6, "injection": 2}
TOTAL = sum(EXPECT.values())
FIELDS = ("id", "type", "question", "gold_answer", "gold_snippets", "must_refuse")
PLACEHOLDER = ("...", "…", "⋯", "略")


class Ctx:
    def __init__(self, target: Path):
        self.path = target / "evals" / "rag_v2.jsonl"
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.total_lines = len(lines)
        self.rows: list[dict] = []
        self.parse_err: list[tuple[int, str]] = []
        for i, line in enumerate(lines, 1):
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
                self.parse_err.append((i, f"顶层是 {type(row).__name__}，不是对象"))

    def of(self, t: str) -> list[dict]:
        return [r for r in self.rows if r.get("type") == t]


# ---------- 文件层 ----------
def c1_parse(ctx: Ctx) -> str:
    assert not ctx.parse_err, (
        "有 " + str(len(ctx.parse_err)) + " 行不是合法 JSON："
        + "; ".join(f"第 {i} 行 {msg[:70]}" for i, msg in ctx.parse_err[:3])
    )
    return f"{len(ctx.rows)} 行全部可解析"


def c2_count(ctx: Ctx) -> str:
    assert len(ctx.rows) == TOTAL, (
        f"实际 {len(ctx.rows)} 条，卡里要求 {TOTAL} 条。"
        "30 条是「能看出趋势」的最小规模：10 条时一次翻转就占 10%，波动会盖住信号"
    )
    return f"{TOTAL} 条"


def c3_no_blank(ctx: Ctx) -> str:
    blank = [i for i, ln in enumerate(ctx.path.read_text(encoding="utf-8").splitlines(), 1) if not ln.strip()]
    assert not blank, f"第 {blank[:5]} 行是空行——JSONL 里空行会被某些 loader 当成坏行整批失败"
    return "无空行"


# ---------- 字段层 ----------
def c4_fields(ctx: Ctx) -> str:
    miss = []
    for r in ctx.rows:
        lack = [f for f in FIELDS if f not in r]
        if lack:
            miss.append(f"{r.get('id', '?')} 缺 {lack}")
    assert not miss, "字段不全：" + "; ".join(miss[:4])
    return f"六个字段齐全（{len(ctx.rows)} 条）"


def c5_id_unique(ctx: Ctx) -> str:
    ids = [r.get("id") for r in ctx.rows]
    dup = {i for i in ids if ids.count(i) > 1}
    assert not dup, f"id 重复：{sorted(dup)[:5]}——挖出来的 case 要能对上具体是哪一条"
    bad = [i for i in ids if not re.fullmatch(r"v2-\d{2,3}", str(i))]
    assert not bad, f"id 不合 v2-NN 格式：{bad[:5]}"
    return f"{len(set(ids))} 个 id 唯一"


def c6_question_unique(ctx: Ctx) -> str:
    qs = [str(r.get("question", "")).strip() for r in ctx.rows]
    dup = {q for q in qs if qs.count(q) > 1}
    assert not dup, f"question 重复：{sorted(dup)[:3]}——同一个问题占两格，等于少一条"
    short = [(r.get("id"), q) for r, q in zip(ctx.rows, qs) if len(q) < 6]
    assert not short, f"question 太短（<6 字）：{short[:3]}"
    return "问题互不重复"


# ---------- 类型分布 ----------
def c7_all_types(ctx: Ctx) -> str:
    got = {r.get("type") for r in ctx.rows}
    lack = set(EXPECT) - got
    assert not lack, f"缺类型 {sorted(lack)}——五类各自测一种失败模式，缺一类就是缺一种视角"
    return f"五类都有：{sorted(got)}"


def c8_counts(ctx: Ctx) -> str:
    diff = []
    for t, want in EXPECT.items():
        got = len(ctx.of(t))
        if got != want:
            diff.append(f"{t} {got}/{want}")
    assert not diff, (
        "条数不对：" + "、".join(diff) + "。"
        "分布变了，总通过率的含义就变了——分类型报通过率的前提是分类型条数固定"
    )
    return "、".join(f"{t} {len(ctx.of(t))}" for t in EXPECT)


def c9_no_extra_type(ctx: Ctx) -> str:
    extra = {r.get("type") for r in ctx.rows} - set(EXPECT)
    assert not extra, (
        f"多出类型 {sorted(extra)}：多一类而条数不变，等于从五类里挪走了名额，"
        "CONTRACT 里的分布就对不上了"
    )
    return "没有第六种类型"


# ---------- 语义 ----------
def c10_unanswerable(ctx: Ctx) -> str:
    for r in ctx.of("unanswerable"):
        assert r.get("must_refuse") is True, (
            f"{r.get('id')} 是 unanswerable 但 must_refuse={r.get('must_refuse')!r}——"
            "这条就永远判不出「该拒的拒了」"
        )
        assert not r.get("gold_snippets"), (
            f"{r.get('id')} 是 unanswerable 却给了 gold_snippets={r.get('gold_snippets')!r}——"
            "既然语料里没有能答的片段，给片段等于把答案喂进去了"
        )
    return f"{len(ctx.of('unanswerable'))} 条都标了拒答"


def c11_others_not_refuse(ctx: Ctx) -> str:
    bad = [r.get("id") for r in ctx.rows
           if r.get("type") != "unanswerable" and r.get("must_refuse") is not False]
    assert not bad, f"这些可答题的 must_refuse 不是 false：{bad[:5]}——拒答率会凭空变高"
    return "可答题都标了 must_refuse=false"


def c12_multi_hop_snippets(ctx: Ctx) -> str:
    for r in ctx.of("multi_hop"):
        n = len(r.get("gold_snippets") or [])
        assert n >= 2, (
            f"{r.get('id')} 的 gold_snippets 只有 {n} 段——"
            "多跳的定义就是至少跨两段，单源说明这题其实是 fact"
        )
    return "多跳都跨了至少两段"


def c13_fact_snippets(ctx: Ctx) -> str:
    for t in ("fact", "precise"):
        for r in ctx.of(t):
            assert len(r.get("gold_snippets") or []) >= 1, (
                f"{r.get('id')}（{t}）没有 gold_snippets——"
                "没有出处就无法区分「答对了」和「猜对了」"
            )
    return "事实型/精确串都有出处"


# ---------- 防抄样例 ----------
def c14_not_placeholder(ctx: Ctx) -> str:
    for r in ctx.rows:
        for field in ("question", "gold_answer"):
            v = str(r.get(field, ""))
            hit = [p for p in PLACEHOLDER if p in v]
            assert not hit, (
                f"{r.get('id')} 的 {field} 里有占位符 {hit}——"
                "手册里那条是格式样例，照抄等于测试集里放了一个测不了的空壳"
            )
        ga = str(r.get("gold_answer", "")).strip()
        if r.get("type") != "unanswerable":
            assert ga, f"{r.get('id')} 的 gold_answer 是空的"
        assert ga != str(r.get("question", "")).strip(), (
            f"{r.get('id')} 的 gold_answer 和 question 一模一样"
        )
    return "没有占位符，答案与问题不重复"


CHECKS = [
    ("每行可解析", c1_parse),
    ("正好 30 条", c2_count),
    ("没有空行", c3_no_blank),
    ("六个字段齐全", c4_fields),
    ("id 唯一且格式统一", c5_id_unique),
    ("question 互不重复", c6_question_unique),
    ("五类都有", c7_all_types),
    ("每类条数对得上", c8_counts),
    ("没有第六种类型", c9_no_extra_type),
    ("不可答都标了拒答", c10_unanswerable),
    ("可答题不标拒答", c11_others_not_refuse),
    ("多跳至少跨两段", c12_multi_hop_snippets),
    ("事实型都有出处", c13_fact_snippets),
    ("没有占位符", c14_not_placeholder),
]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="判 P2-12 的 30 条测试集")
    ap.add_argument("--target", default=".", help="项目根目录（含 evals/）")
    args, rest = ap.parse_known_args()

    target = Path(args.target).expanduser().resolve()
    path = target / "evals" / "rag_v2.jsonl"
    if not path.is_file():
        return exit_missing(
            f"× 在 {target} 下没找到 evals/rag_v2.jsonl",
            "  用 --target 指到项目根目录",
            "  CONTRACT §1 要求 30 行 JSONL 落在这里",
        )
    try:
        ctx = Ctx(target)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return exit_missing(f"× 读文件失败：{type(exc).__name__}: {exc}")

    return run_all(
        "P2-12 判分 · 30 条测试集",
        CHECKS,
        ctx,
        argv=rest,
        subtitle=f"目标 {path}",
        footer=(
            "注意：这里判「分布与字段」，不判「题目质量」。\n"
            "      gold_answer 是不是从语料里抄的，只能人对着原文核——卡里那句验收要求的就是这件事。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
