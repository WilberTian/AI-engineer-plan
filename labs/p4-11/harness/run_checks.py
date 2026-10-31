"""P4-11 判分：四段埋点与分位数算得对不对。

被判对象 `agentlab/latency.py`：`Timing`（四个时间点 + 三个派生属性）和 `percentile()`。

这一层全是算术，能精确判。判三件事：

1. 派生值是不是从**时间点**算出来的（多存一个字段，就多一处会不一致）
2. 没设 `t_first_token` 时（非流式）退化成什么
3. 分位数是**最近邻**还是插值——几十条样本时插值出来的 p95 是假精度

    python3 labs/p4-11/harness/run_checks.py --target ~/code/agentlab-project
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "_shared"))
from checkkit import exit_missing, run_all  # noqa: E402


class Ctx:
    def __init__(self, target: Path):
        self.target = target
        sys.path.insert(0, str(target))
        from agentlab import latency as mod  # noqa: PLC0415

        self.mod = mod
        self.Timing = mod.Timing
        self.percentile = mod.percentile

    def t(self, start=0.0, first=0.0, end=0.0, tool=0.0):
        return self.Timing(t_start=start, t_first_token=first, t_end=end, tool_ms=tool)


# ---------- 四段 ----------
def c1_ttft(ctx: Ctx) -> str:
    got = ctx.t(start=100.0, first=100.35, end=101.0).ttft_ms
    assert abs(got - 350.0) < 0.5, f"TTFT 应为 350ms，实为 {got}"
    return "ttft = 首 token 时间 - 开始时间"


def c2_gen(ctx: Ctx) -> str:
    got = ctx.t(start=100.0, first=100.35, end=101.0).gen_ms
    assert abs(got - 650.0) < 0.5, f"生成段应为 650ms，实为 {got}"
    return "gen = 结束时间 - 首 token 时间"


def c3_total(ctx: Ctx) -> str:
    got = ctx.t(start=100.0, first=100.35, end=101.0).total_ms
    assert abs(got - 1000.0) < 0.5, f"总时长应为 1000ms，实为 {got}"
    return "total = 结束时间 - 开始时间"


def c4_no_stream_ttft(ctx: Ctx) -> str:
    """非流式拿不到首 token 时间，TTFT 该是 0（不知道），不是「等于总时长」。"""
    got = ctx.t(start=100.0, first=0.0, end=101.0).ttft_ms
    assert got == 0, f"没设首 token 时 ttft 应为 0，实为 {got}——它会被当成「首字很慢」写进报告"
    return "非流式 ttft = 0"


def c5_no_stream_gen(ctx: Ctx) -> str:
    got = ctx.t(start=100.0, first=0.0, end=101.0).gen_ms
    assert got == 0, f"没设首 token 时 gen 应为 0，实为 {got}"
    return "非流式 gen = 0"


def c6_total_includes_tool(ctx: Ctx) -> str:
    """total 是从开始到结束的全跨度，工具时间在里面（tool_ms 是独立统计的）。"""
    got = ctx.t(start=0.0, first=0.5, end=2.0, tool=0.8).total_ms
    assert abs(got - 2000.0) < 0.5, f"total 应为 2000ms（含工具时间），实为 {got}"
    return "total 覆盖工具时间"


def c7_no_negative(ctx: Ctx) -> str:
    """时钟乱序（或 t_end 还没设）时不能出负的时长——报告里出现 -800ms 会让人怀疑整个埋点。

    参考实现是这条红：`gen_ms` 直接在 `t_end - t_first_token` 上乘 1000，没有下界。
    """
    t = ctx.t(start=0.0, first=0.8, end=0.0)     # 首 token 记了，结束时间还没记
    assert t.gen_ms >= 0, f"时间点乱序时 gen_ms 算出了 {t.gen_ms}ms（负数）"
    assert t.ttft_ms >= 0, f"ttft_ms 算出了 {t.ttft_ms}ms（负数）"
    return "时间点乱序时不出负值"


def c8_derived_not_stored(ctx: Ctx) -> str:
    """派生值必须随源时间点变化——如果 ttft 是构造时算好存起来的，改 t_start 就不会变。"""
    t = ctx.t(start=0.0, first=0.5, end=1.0)
    before = t.ttft_ms
    t.t_start = 0.25
    after = t.ttft_ms
    assert after != before, "改了 t_start 之后 ttft 没变——说明它是存下来的字段，不是算出来的"
    return f"改源时间点后 ttft {before} → {after}"


# ---------- 分位数 ----------
def c9_pct_empty(ctx: Ctx) -> str:
    assert ctx.percentile([], 95) == 0.0, "空列表的 p95 应为 0（不能除零、不能抛异常）"
    return "空列表 → 0.0"


def c10_pct_single(ctx: Ctx) -> str:
    got = ctx.percentile([42.0], 95)
    assert got == 42.0, f"单元素时任何分位都应返回该值，实为 {got}"
    return "单元素 → 该值"


def c11_pct_min_max(ctx: Ctx) -> str:
    xs = [5.0, 1.0, 9.0, 3.0]
    assert ctx.percentile(xs, 0) == 1.0, f"p0 应为最小值 1.0，实为 {ctx.percentile(xs, 0)}"
    assert ctx.percentile(xs, 100) == 9.0, f"p100 应为最大值 9.0，实为 {ctx.percentile(xs, 100)}"
    return "p0 = min，p100 = max"


def c12_pct_median_odd(ctx: Ctx) -> str:
    got = ctx.percentile([10.0, 20.0, 30.0], 50)
    assert got == 20.0, f"三个数的 p50 应为中间那个 20，实为 {got}"
    return "奇数样本 p50 取中间值"


def c13_pct_nearest_not_interpolated(ctx: Ctx) -> str:
    """20 个样本（0..19）的 p95：最近邻应取 18；线性插值会得 18.05（假精度）。

    为什么这条值得判：样本只有几十条时，插值出来的小数会让人以为精度很高，
    而实际上「第 19 名和第 20 名差多少」才是真正的信息量。
    """
    xs = [float(i) for i in range(20)]
    got = ctx.percentile(xs, 95)
    assert got == 18.0, (
        f"20 个样本的 p95 应为 18.0（索引 18，第二大的值），实为 {got}\n"
        "          18.05 说明用了线性插值——几十条样本时这是假精度"
    )
    return "p95 = 18（最近邻，不插值）"


def c14_pct_monotonic(ctx: Ctx) -> str:
    xs = [3.0, 1.0, 4.0, 1.5, 9.0, 2.6, 5.3, 5.9, 7.9, 2.7]
    seq = [ctx.percentile(xs, p) for p in (0, 25, 50, 75, 95, 100)]
    assert seq == sorted(seq), f"分位数不单调：{seq}——函数写错了"
    return f"p0..p100 = {seq}"


def c15_pct_no_mutate(ctx: Ctx) -> str:
    xs = [3.0, 1.0, 2.0]
    ctx.percentile(xs, 50)
    assert xs == [3.0, 1.0, 2.0], f"percentile 改了入参顺序：{xs}——调用方后续统计会错"
    return "percentile 不修改入参"


CHECKS = [
    ("ttft 由首 token 时间算出", c1_ttft),
    ("生成段由结束与首 token 算出", c2_gen),
    ("total 是全程跨度", c3_total),
    ("非流式时 ttft 为 0", c4_no_stream_ttft),
    ("非流式时生成段为 0", c5_no_stream_gen),
    ("total 包含工具时间", c6_total_includes_tool),
    ("时间点乱序不出负值", c7_no_negative),
    ("派生值是算出来的不是存下来的", c8_derived_not_stored),
    ("空列表 p95 为 0", c9_pct_empty),
    ("单元素分位数等于该值", c10_pct_single),
    ("p0/p100 取最小最大", c11_pct_min_max),
    ("奇数样本 p50 取中间值", c12_pct_median_odd),
    ("p95 用最近邻不插值", c13_pct_nearest_not_interpolated),
    ("分位数单调", c14_pct_monotonic),
    ("percentile 不改入参", c15_pct_no_mutate),
]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="判 P4-11 的延迟分解")
    ap.add_argument("--target", default=".", help="项目根目录（含 agentlab/）")
    args, rest = ap.parse_known_args()

    target = Path(args.target).expanduser().resolve()
    if not (target / "agentlab" / "latency.py").is_file():
        return exit_missing(
            f"× 在 {target} 下没找到 agentlab/latency.py",
            "  用 --target 指到项目根目录",
            "  CONTRACT §1 要求 Timing 与 percentile 在这里",
        )
    try:
        ctx = Ctx(target)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return exit_missing(f"× 导入失败：{type(exc).__name__}: {exc}")

    return run_all(
        "P4-11 判分 · 四段埋点与分位数",
        CHECKS,
        ctx,
        argv=rest,
        subtitle=f"目标 {target}",
        footer=(
            "注意：这里判的是算术。\n"
            "      卡里验收要求「能回答 p95 是 X ms、最大一段是 Y」——那要真跑 20 条 query，离线判不了。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
