"""P4-13 判分：成本分解表算得对不对。

被判对象 `scripts/breakdown.py`：`breakdown(trace) -> list[(name, cost, ms)]`，
按 span 名字聚合成本与耗时，按成本降序。

这是那道面试题的第一步。第一步做错，后面三步全在优化错的地方——所以它值得判。

    python3 labs/p4-13/harness/run_checks.py --target ~/code/agentlab-project
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "_shared"))
from checkkit import exit_missing, run_all  # noqa: E402


def span(kind: str, name: str, in_tok: int = 0, out_tok: int = 0, ms: int = 0):
    return SimpleNamespace(kind=kind, name=name, in_tok=in_tok, out_tok=out_tok, ms=ms)


def trace(*spans):
    return SimpleNamespace(spans=list(spans))


class Ctx:
    def __init__(self, target: Path):
        self.target = target
        sys.path.insert(0, str(target))
        import importlib.util  # noqa: PLC0415

        p = target / "scripts" / "breakdown.py"
        if not p.is_file():
            p = target / "breakdown.py"
        spec = importlib.util.spec_from_file_location("breakdown_under_test", p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        self.mod = mod
        self.breakdown = mod.breakdown
        self.COST_IN = mod.COST_IN
        self.COST_OUT = mod.COST_OUT


def rows(result):
    """把返回值统一成 {name: (cost, ms)}，同时校验三元组形状。"""
    out = {}
    for r in result:
        assert len(r) == 3, f"每条结果应是 (name, cost, ms) 三元组，实际 {r!r}"
        name, cost, ms = r
        assert isinstance(name, str), f"名字应是字符串，实际 {type(name).__name__}"
        assert isinstance(cost, (int, float)), f"成本应是数字，实际 {type(cost).__name__}"
        assert isinstance(ms, (int, float)), f"耗时应是数字，实际 {type(ms).__name__}"
        out[name] = (float(cost), float(ms))
    return out


# ---------- 成本公式与聚合 ----------
def c1_cost_formula(ctx: Ctx) -> str:
    r = rows(ctx.breakdown(trace(span("llm", "plan", in_tok=1000, out_tok=200, ms=500))))
    want = 1000 * ctx.COST_IN + 200 * ctx.COST_OUT
    got = r["plan"][0]
    assert abs(got - want) < 1e-12, f"成本公式不对：期望 {want:.10f}，实际 {got:.10f}"
    return f"plan = ${got:.8f}"


def c2_aggregate_cost(ctx: Ctx) -> str:
    """同名 span 要合并——agent 里同一个 self_check 会被调很多次，分开列没法排序。"""
    r = rows(ctx.breakdown(trace(
        span("llm", "self_check", in_tok=1000, ms=100),
        span("llm", "self_check", in_tok=3000, ms=300),
    )))
    want = 4000 * ctx.COST_IN
    assert abs(r["self_check"][0] - want) < 1e-12, (
        f"同名 span 没合并：期望 ${want:.10f}，实际 ${r['self_check'][0]:.10f}"
    )
    assert len(r) == 1, f"同名 span 出现在多行：{list(r)}"
    return f"两次 self_check 合并为 ${r['self_check'][0]:.8f}"


def c3_aggregate_ms(ctx: Ctx) -> str:
    r = rows(ctx.breakdown(trace(
        span("llm", "a", in_tok=10, ms=120),
        span("llm", "a", in_tok=10, ms=80),
    )))
    assert r["a"][1] == 200, f"同名 span 的耗时没累加：{r['a'][1]}"
    return "耗时累加正确"


def c4_sorted_desc(ctx: Ctx) -> str:
    res = ctx.breakdown(trace(
        span("llm", "cheap", in_tok=100, ms=10),
        span("llm", "expensive", in_tok=10000, ms=10),
        span("llm", "mid", in_tok=2000, ms=10),
    ))
    names = [r[0] for r in res]
    assert names == ["expensive", "mid", "cheap"], f"没按成本降序：{names}"
    return f"降序：{names}"


def c5_only_llm_counted(ctx: Ctx) -> str:
    """工具执行本身不产生 token 成本，不该按 token 计（ms 仍要记，见第 9 条）。"""
    r = rows(ctx.breakdown(trace(
        span("llm", "plan", in_tok=1000, ms=100),
        span("tool", "read_file", in_tok=99999, out_tok=99999, ms=50),
    )))
    assert "read_file" not in r or r["read_file"][0] == 0, (
        f"工具 span 被算进了 token 成本：read_file = ${r.get('read_file', (0,))[0]:.8f}"
    )
    return "工具 span 不产生 token 成本"


def c6_retrieval_not_dropped(ctx: Ctx) -> str:
    """卡里要求「拆到每一次检索、每一次重排」，参考实现只留 llm，把这两类静默丢了。

    成本记 0 也行（检索可能没有 token 计价），但**名字必须出现在表里**——
    否则你会得出「钱全花在模型上」这个假结论，而真实的延迟大头可能在重排。
    """
    r = rows(ctx.breakdown(trace(
        span("llm", "plan", in_tok=1000, ms=100),
        span("retrieval", "hybrid_search", ms=800),
        span("rerank", "cross_encoder", ms=1200),
    )))
    missing = [n for n in ("hybrid_search", "cross_encoder") if n not in r]
    assert not missing, (
        f"这些 span 被丢掉了：{missing}\n"
        "          卡里明确要求拆到「每一次检索、每一次重排」。修法：成本按 0 也要出行，"
        "          否则耗时分布看不见，你会去优化一个不是瓶颈的地方"
    )
    return "检索与重排都在表里"


# ---------- 边界 ----------
def c7_empty(ctx: Ctx) -> str:
    assert list(ctx.breakdown(trace())) == [], "空 trace 应返回空列表"
    return "空 trace → []"


def c8_only_tools(ctx: Ctx) -> str:
    """没有任何 llm span 时不能除零崩掉（参考实现的 `or 1` 就是干这个的）。"""
    ctx.breakdown(trace(span("tool", "x", ms=10)))
    return "全工具 span 不崩"


def c9_single_share(ctx: Ctx) -> str:
    r = rows(ctx.breakdown(trace(span("llm", "only", in_tok=500, ms=10))))
    assert len(r) == 1 and r["only"][0] > 0, f"单 span 的结果不对：{r}"
    return "单 span 正常"


def c10_pure(ctx: Ctx) -> str:
    tr = trace(span("llm", "a", in_tok=100, ms=1), span("llm", "b", in_tok=200, ms=2))
    before = [(s.name, s.in_tok, s.ms) for s in tr.spans]
    ctx.breakdown(tr)
    after = [(s.name, s.in_tok, s.ms) for s in tr.spans]
    assert before == after, f"breakdown 改了入参 trace：{before} → {after}"
    return "不修改入参"


def c11_repeatable(ctx: Ctx) -> str:
    tr = trace(span("llm", "a", in_tok=100, ms=1), span("llm", "b", in_tok=200, ms=2))
    a = [(r[0], round(r[1], 12)) for r in ctx.breakdown(tr)]
    b = [(r[0], round(r[1], 12)) for r in ctx.breakdown(tr)]
    assert a == b, f"同一 trace 两次分解结果不同：{a} vs {b}"
    return "同一输入结果一致"


def c12_zero_token_no_crash(ctx: Ctx) -> str:
    ctx.breakdown(trace(span("llm", "z", in_tok=0, out_tok=0, ms=0)))
    return "零 token 不崩"


CHECKS = [
    ("成本 = in×单价 + out×单价", c1_cost_formula),
    ("同名 span 合并成本", c2_aggregate_cost),
    ("同名 span 累加耗时", c3_aggregate_ms),
    ("按成本降序排列", c4_sorted_desc),
    ("工具 span 不按 token 计价", c5_only_llm_counted),
    ("检索/重排 span 不被静默丢掉", c6_retrieval_not_dropped),
    ("空 trace 返回空列表", c7_empty),
    ("全工具 span 不除零崩", c8_only_tools),
    ("单 span 正常", c9_single_share),
    ("不修改入参", c10_pure),
    ("同一输入结果一致", c11_repeatable),
    ("零 token 不崩", c12_zero_token_no_crash),
]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="判 P4-13 的成本分解")
    ap.add_argument("--target", default=".", help="项目根目录（含 scripts/breakdown.py）")
    args, rest = ap.parse_known_args()

    target = Path(args.target).expanduser().resolve()
    if not (target / "scripts" / "breakdown.py").is_file() and not (target / "breakdown.py").is_file():
        return exit_missing(
            f"× 在 {target} 下没找到 scripts/breakdown.py",
            "  用 --target 指到项目根目录（脚本也可以放在根目录）",
            "  CONTRACT §1 要求 breakdown(trace) 与 COST_IN / COST_OUT 在这里",
        )
    try:
        ctx = Ctx(target)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return exit_missing(f"× 导入失败：{type(exc).__name__}: {exc}")

    return run_all(
        "P4-13 判分 · 成本分解",
        CHECKS,
        ctx,
        argv=rest,
        subtitle=f"目标 {target}",
        footer=(
            "注意：这里判的是分解表算得对不对。\n"
            "      那道面试题本身（25 分钟讲完、四步顺序）判不了——它考的是决策顺序，不是代码。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
