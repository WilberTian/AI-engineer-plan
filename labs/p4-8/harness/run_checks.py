"""P4-8 判分：成本记账算得对不对。

被判对象 `agentlab/cost.py`：`Usage.cost_usd()` + `summarize()`。

这一层全是算术，所以**能精确判**——没有「大概差不多」。判的是三件事：

1. 单位对不对（美元 / 百万 token，差 1000 倍是常见错）
2. 缓存那部分有没有**从 input 里扣掉**（不扣就是同一批 token 算两遍）
3. 拿不到价格时返回 0 还是猜一个数（猜出来的「便宜」比 0 更危险）

    python3 labs/p4-8/harness/run_checks.py --target ~/code/agentlab-project
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "_shared"))
from checkkit import exit_missing, run_all  # noqa: E402

TOL = 1e-9


class Ctx:
    def __init__(self, target: Path):
        self.target = target
        sys.path.insert(0, str(target))
        from agentlab import cost as mod  # noqa: PLC0415

        self.mod = mod
        self.Usage = mod.Usage
        self.summarize = mod.summarize
        self.PRICES = mod.PRICES
        # 取一个有价的价格档，不锁定具体模型名（价格表是你的）
        self.model = "gpt-4.1-mini" if "gpt-4.1-mini" in self.PRICES else next(iter(self.PRICES))
        self.price = self.PRICES[self.model]

    def u(self, **kw):
        kw.setdefault("model", self.model)
        return self.Usage(**kw)


def close(a: float, b: float, msg: str) -> None:
    assert abs(a - b) < TOL, f"{msg}：期望 {b:.9f}，实际 {a:.9f}（差 {abs(a - b):.9f}）"


# ---------- 单位与基本公式 ----------
def c1_zero(ctx: Ctx) -> str:
    close(ctx.u().cost_usd(), 0.0, "零 token 的成本")
    return "0 token → 0"


def c2_input_only(ctx: Ctx) -> str:
    """1000 输入 token 的成本 = 1000 × in / 1e6，不是 /1e3。"""
    got = ctx.u(input_tokens=1000).cost_usd()
    want = 1000 * ctx.price["in"] / 1_000_000
    close(got, want, "纯输入 1000 token")
    return f"{ctx.model} 1000 in = ${got:.8f}"


def c3_output_only(ctx: Ctx) -> str:
    got = ctx.u(output_tokens=1000).cost_usd()
    want = 1000 * ctx.price["out"] / 1_000_000
    close(got, want, "纯输出 1000 token")
    return f"1000 out = ${got:.8f}"


def c4_units_not_per_1k(ctx: Ctx) -> str:
    """百万 token 单价表配 /1000 的除数，是这里最常见的错——成本会虚高 1000 倍。"""
    got = ctx.u(input_tokens=1_000_000).cost_usd()
    want = ctx.price["in"]
    close(got, want, "100 万输入 token 应正好等于单价")
    return f"1M in = ${got:.4f}（等于单价 {ctx.price['in']}）"


# ---------- 缓存那部分 ----------
def c5_cached_is_subtracted(ctx: Ctx) -> str:
    """cached 必须从 input 里扣掉再按缓存价算；不扣就是同一批 token 算两遍。"""
    full = ctx.u(input_tokens=1000).cost_usd()
    half = ctx.u(input_tokens=1000, cached_tokens=400).cost_usd()
    want = (600 * ctx.price["in"] + 400 * ctx.price["cached_in"]) / 1_000_000
    close(half, want, "1000 in 其中 400 命中缓存")
    assert half < full, f"命中缓存反而更贵（{half:.8f} ≥ {full:.8f}）——说明没按 cached_in 计价"
    return f"命中 400 后 ${half:.8f} < 未命中 ${full:.8f}"


def c6_all_cached(ctx: Ctx) -> str:
    got = ctx.u(input_tokens=1000, cached_tokens=1000).cost_usd()
    want = 1000 * ctx.price["cached_in"] / 1_000_000
    close(got, want, "全部命中缓存")
    return f"全命中 = ${got:.8f}"


def c7_cached_over_input(ctx: Ctx) -> str:
    """厂商偶尔会给出 cached > input 的脏数，不能因此算出负成本。"""
    got = ctx.u(input_tokens=100, cached_tokens=500).cost_usd()
    assert got >= 0, f"cached > input 时算出了负成本 ${got:.8f}"
    return f"cached > input 时 ${got:.8f}（不为负）"


# ---------- 拿不到价格 ----------
def c8_unknown_model_zero(ctx: Ctx) -> str:
    """价格表里没有就返回 0，不要猜。猜出来的「便宜」是假象。"""
    got = ctx.Usage(model="some-model-nobody-priced", input_tokens=1_000_000).cost_usd()
    close(got, 0.0, "未知模型")
    return "未知模型 → 0.0（不猜价）"


def c9_unknown_model_not_raise(ctx: Ctx) -> str:
    try:
        ctx.Usage(model="", input_tokens=10).cost_usd()
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(
            f"未知模型抛了 {type(exc).__name__}——记账代码崩在一条没定价的模型上，"
            "整个 eval 报告就没了"
        ) from exc
    return "未知模型不抛异常"


# ---------- 线性 ----------
def c10_linear(ctx: Ctx) -> str:
    one = ctx.u(input_tokens=777, output_tokens=333, cached_tokens=100).cost_usd()
    three = ctx.u(input_tokens=777 * 3, output_tokens=333 * 3, cached_tokens=100 * 3).cost_usd()
    close(three, one * 3, "三倍用量")
    return "成本随用量线性"


# ---------- summarize ----------
def c11_total(ctx: Ctx) -> str:
    us = [ctx.u(input_tokens=1000), ctx.u(input_tokens=2000, cached_tokens=500)]
    s = ctx.summarize(us)
    close(s["total_usd"], sum(u.cost_usd() for u in us), "总成本")
    return f"总成本 = 逐条之和 ${s['total_usd']:.8f}"


def c12_token_sums(ctx: Ctx) -> str:
    us = [ctx.u(input_tokens=1000, output_tokens=100), ctx.u(input_tokens=2000, output_tokens=50)]
    s = ctx.summarize(us)
    assert s["input_tokens"] == 3000, f"input 合计应为 3000，实为 {s['input_tokens']}"
    assert s["output_tokens"] == 150, f"output 合计应为 150，实为 {s['output_tokens']}"
    return "in/out 合计正确"


def c13_cache_hit_rate(ctx: Ctx) -> str:
    s = ctx.summarize([ctx.u(input_tokens=1000, cached_tokens=620)])
    close(s["cache_hit_rate"], 0.62, "命中率")
    return f"命中率 {s['cache_hit_rate']}"


def c14_empty(ctx: Ctx) -> str:
    s = ctx.summarize([])
    assert s["n_calls"] == 0, f"空列表的 n_calls 应为 0，实为 {s['n_calls']}"
    close(s["total_usd"], 0.0, "空列表总成本")
    close(s["cache_hit_rate"], 0.0, "空列表命中率（不能除零崩）")
    return "空列表：0 成本 / 0 命中率，不崩"


def c15_n_calls(ctx: Ctx) -> str:
    s = ctx.summarize([ctx.u(input_tokens=1) for _ in range(7)])
    assert s["n_calls"] == 7, f"n_calls 应为调用次数 7，实为 {s['n_calls']}（是不是在数 token？）"
    return "n_calls 数的是调用次数"


def c16_pure(ctx: Ctx) -> str:
    """summarize 不该改入参——否则同一个 usage 列表第二次汇总会翻倍。"""
    us = [ctx.u(input_tokens=1000, output_tokens=100)]
    before = us[0].input_tokens
    ctx.summarize(us)
    assert us[0].input_tokens == before, f"summarize 改了入参：{before} → {us[0].input_tokens}"
    return "summarize 无副作用"


CHECKS = [
    ("零 token 成本为 0", c1_zero),
    ("纯输入按百万 token 单价算", c2_input_only),
    ("纯输出按百万 token 单价算", c3_output_only),
    ("单位是百万 token（不是每千）", c4_units_not_per_1k),
    ("缓存部分从 input 里扣掉再按缓存价算", c5_cached_is_subtracted),
    ("全部命中缓存时只算缓存价", c6_all_cached),
    ("cached > input 时不出负成本", c7_cached_over_input),
    ("未知模型返回 0 而不是猜价", c8_unknown_model_zero),
    ("未知模型不抛异常", c9_unknown_model_not_raise),
    ("成本随用量线性", c10_linear),
    ("总成本等于逐条之和", c11_total),
    ("input/output 合计正确", c12_token_sums),
    ("缓存命中率 = cached/input", c13_cache_hit_rate),
    ("空列表不除零", c14_empty),
    ("n_calls 数的是调用次数", c15_n_calls),
    ("summarize 不改入参", c16_pure),
]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="判 P4-8 的成本记账")
    ap.add_argument("--target", default=".", help="项目根目录（含 agentlab/）")
    args, rest = ap.parse_known_args()

    target = Path(args.target).expanduser().resolve()
    if not (target / "agentlab" / "cost.py").is_file():
        return exit_missing(
            f"× 在 {target} 下没找到 agentlab/cost.py",
            "  用 --target 指到项目根目录",
            "  CONTRACT §1 要求 Usage / summarize / PRICES 都在这个文件里",
        )
    try:
        ctx = Ctx(target)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return exit_missing(f"× 导入失败：{type(exc).__name__}: {exc}")

    return run_all(
        "P4-8 判分 · 成本记账",
        CHECKS,
        ctx,
        argv=rest,
        subtitle=f"目标 {target}（价格用你自己的表：{ctx.model}）",
        footer=(
            "注意：这里判的是算术。\n"
            "      卡里验收还要求「能说出成本里 X% 来自输入 token」——那要在真跑一次 eval 后看报告，离线判不了。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
