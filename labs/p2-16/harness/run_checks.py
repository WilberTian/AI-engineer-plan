"""P2-16 判分：通过率之外的那几个数算得对不对。

被判对象 `evals/metrics.py`：`pass_at_k` / `pass_pow_k` / `attribute` / `boot_ci` /
`paired_delta` / `tally`。

这一层全是定义问题，所以**能精确判**——而且必须精确判。这几个数一旦算错，
你后面所有的比较（A 方案 vs B 方案、改前 vs 改后）都建立在错的基线上，
而且它们不会报错，只会给你一个看起来合理的百分比。

    python3 labs/p2-16/harness/run_checks.py --target ~/code/agentlab-project
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "_shared"))
from checkkit import exit_missing, run_all  # noqa: E402


class Ctx:
    def __init__(self, target: Path):
        self.target = target
        sys.path.insert(0, str(target))
        sys.path.insert(0, str(target / "evals"))
        try:
            import metrics as mod  # noqa: PLC0415
        except ImportError:
            from evals import metrics as mod  # noqa: PLC0415

        self.mod = mod
        self.Run = mod.Run


# ---------- pass@k / pass^k ----------
def c1_pass_at_k(ctx: Ctx) -> str:
    """任一次成功即算成功：能力上限。"""
    runs = {"a": [False, False, True], "b": [False, False, False]}
    got = ctx.mod.pass_at_k(runs, 3)
    assert abs(got - 0.5) < 1e-9, f"pass@3 应为 0.5（2 题里 1 题曾成功），实为 {got}"
    return "pass@3 = 0.5"


def c2_pass_at_k_only_first_k(ctx: Ctx) -> str:
    """看前 k 次，不是全部。第 3 次成功但 k=2 时不该算成功。"""
    runs = {"a": [False, False, True]}
    got = ctx.mod.pass_at_k(runs, 2)
    assert abs(got) < 1e-9, f"pass@2 应为 0，实为 {got}——它把第 3 次也算进去了"
    return "pass@2 只看前两次"


def c3_pass_pow_k(ctx: Ctx) -> str:
    """连续 k 次都成功：业务可靠性。"""
    runs = {"a": [True, True, True], "b": [True, False, True]}
    got = ctx.mod.pass_pow_k(runs, 3)
    assert abs(got - 0.5) < 1e-9, f"pass^3 应为 0.5（只有 a 全对），实为 {got}"
    return "pass^3 = 0.5"


def c4_pass_pow_k_short_list(ctx: Ctx) -> str:
    """只跑了 1 次却问 pass^3：不能算成功，也不能崩。"""
    runs = {"a": [True]}
    got = ctx.mod.pass_pow_k(runs, 3)
    assert abs(got) < 1e-9, f"只有 1 次运行却算 pass^3 成功（实为 {got}）——分母没有约束"
    return "次数不足时不算成功"


def c5_two_metrics_differ(ctx: Ctx) -> str:
    """同一批数据，两个指标必须给出不同答案——否则有一个是假的。"""
    runs = {f"t{i}": ([True, False, False] if i < 7 else [False, False, False]) for i in range(10)}
    a = ctx.mod.pass_at_k(runs, 3)
    b = ctx.mod.pass_pow_k(runs, 3)
    assert a > b, f"pass@3={a} 不大于 pass^3={b}——两指标没区分开（7 题都是「一次对两次错」）"
    return f"pass@3={a:.2f} > pass^3={b:.2f}"


# ---------- 失败归因 ----------
def c6_attribute_tool_error(ctx: Ctx) -> str:
    r = ctx.Run("t", False, [{"tool": "read", "error": "timeout"}])
    got = ctx.mod.attribute(r)
    assert "tool_error" in got and "step0" in got, f"应归到 step0 的工具错误，实为 {got!r}"
    return got


def c7_attribute_bad_args(ctx: Ctx) -> str:
    r = ctx.Run("t", False, [{"tool": "read", "args": {"p": 1}, "result": ""}])
    got = ctx.mod.attribute(r)
    assert "bad_args" in got, f"工具调了但没结果，应归到 bad_args，实为 {got!r}"
    return got


def c8_attribute_first_failure(ctx: Ctx) -> str:
    """归到**第一个**出问题的环节，不是最后一个。"""
    r = ctx.Run("t", False, [
        {"tool": "a", "error": "boom"},
        {"tool": "b", "error": "boom2"},
    ])
    got = ctx.mod.attribute(r)
    assert "step0" in got, f"应归到 step0（第一个失败），实为 {got!r}——归到最后一个会误导排查方向"
    return got


def c9_attribute_final_format(ctx: Ctx) -> str:
    """步骤都对、最终答案不合格：要单独一类，不能算成工具失败。"""
    r = ctx.Run("t", False, [{"tool": "a", "result": "ok"}])
    got = ctx.mod.attribute(r)
    assert "final" in got, f"应归到 final 层，实为 {got!r}"
    return got


def c10_attribute_ok(ctx: Ctx) -> str:
    r = ctx.Run("t", True, [{"tool": "a", "result": "ok"}])
    got = ctx.mod.attribute(r)
    assert got == "ok", f"成功的 run 应返回 'ok'，实为 {got!r}"
    return "成功归为 ok"


# ---------- 显著性 ----------
def c11_boot_ci_deterministic(ctx: Ctx) -> str:
    """bootstrap 用 `random.choice`（全局随机），两次调用结果会不同。

    这不是必须修的错，但你得知道：同一份数据两次报告会有细微差别。
    参考实现就是这样，所以这条只判「区间包住中位数、宽度合理」。
    """
    xs = [0.00, 0.10, 0.20, 0.30, 0.45, 0.55, 0.70, 0.85, 0.90, 1.00]
    lo, hi = ctx.mod.boot_ci(xs, 500)
    assert lo <= hi, f"区间反了：{lo} > {hi}"
    assert lo < 0.5 < hi, f"区间 [{lo:.2f}, {hi:.2f}] 没包住数据中位数——bootstrap 写错了"
    return f"CI = [{lo:.2f}, {hi:.2f}]"


def c12_paired_delta(ctx: Ctx) -> str:
    # t2、t4 是「只 A 对」，t3 是「只 B 对」，t1 两边都对（不计）
    a = {"t1": True, "t2": True, "t3": False, "t4": True}
    b = {"t1": True, "t2": False, "t3": True, "t4": False}
    a_only, b_only = ctx.mod.paired_delta(a, b)
    assert (a_only, b_only) == (2, 1), (
        f"应为 (2,1)：t2、t4 只 A 对，t3 只 B 对，两组都对的 t1 不计，实为 {(a_only, b_only)}"
    )
    return "只 A 对=2，只 B 对=1"


def c13_paired_delta_ignores_both(ctx: Ctx) -> str:
    """两边都对/都错的不提供信息，不能算进 delta。"""
    a = {"t1": True, "t2": False}
    b = {"t1": True, "t2": False}
    a_only, b_only = ctx.mod.paired_delta(a, b)
    assert (a_only, b_only) == (0, 0), f"两边一致时应是 (0,0)，实为 {(a_only, b_only)}"
    return "两边一致的题不计入"


# ---------- 验证器四态 ----------
def c14_tally_four_states(ctx: Ctx) -> str:
    cases = [{"id": str(i)} for i in range(4)]
    before = {"0": True, "1": True, "2": False, "3": False}
    after = {"0": True, "1": False, "2": True, "3": False}
    got = ctx.mod.tally(cases, before, after)
    want = {"held": 1, "fixed": 1, "regressed": 1, "still_broken": 1}
    assert got == want, f"四态计数应为 {want}，实为 {got}"
    return "四态各 1"


def c15_tally_regressed_is_separate(ctx: Ctx) -> str:
    """regressed 必须单独报——它是唯一需要立刻回滚的信号，混进总数就看不见了。"""
    cases = [{"id": "a"}, {"id": "b"}]
    got = ctx.mod.tally(cases, {"a": True, "b": True}, {"a": False, "b": False})
    assert got.get("regressed") == 2, f"两条都退步了，regressed 应为 2，实为 {got}"
    assert sum(got.values()) == 2, f"四态之和应等于 case 数 2，实为 {sum(got.values())}"
    return "regressed 单独计数"


def c16_tally_sum_equals_cases(ctx: Ctx) -> str:
    cases = [{"id": str(i)} for i in range(10)]
    before = {str(i): i % 2 == 0 for i in range(10)}
    after = {str(i): i % 3 == 0 for i in range(10)}
    got = ctx.mod.tally(cases, before, after)
    assert sum(got.values()) == 10, f"四态之和 {sum(got.values())} ≠ case 数 10——有 case 被漏掉或重复计"
    return "四态之和 = case 数"


CHECKS = [
    ("pass@k 任一次成功即算成功", c1_pass_at_k),
    ("pass@k 只看前 k 次", c2_pass_at_k_only_first_k),
    ("pass^k 连续 k 次都成功", c3_pass_pow_k),
    ("运行次数不足时不算 pass^k", c4_pass_pow_k_short_list),
    ("两个指标对同一批数据给出不同答案", c5_two_metrics_differ),
    ("归因到工具错误", c6_attribute_tool_error),
    ("归因到参数错", c7_attribute_bad_args),
    ("归因到第一个失败环节", c8_attribute_first_failure),
    ("步骤都对但答案不合格时归到 final", c9_attribute_final_format),
    ("成功的 run 归为 ok", c10_attribute_ok),
    ("bootstrap 区间包住中位数", c11_boot_ci_deterministic),
    ("paired_delta 只数单边翻转", c12_paired_delta),
    ("两边一致的不计入 delta", c13_paired_delta_ignores_both),
    ("四态计数正确", c14_tally_four_states),
    ("regressed 单独计数", c15_tally_regressed_is_separate),
    ("四态之和等于 case 数", c16_tally_sum_equals_cases),
]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="判 P2-16 的评测指标")
    ap.add_argument("--target", default=".", help="项目根目录（含 evals/metrics.py）")
    args, rest = ap.parse_known_args()

    target = Path(args.target).expanduser().resolve()
    if not (target / "evals" / "metrics.py").is_file():
        return exit_missing(
            f"× 在 {target} 下没找到 evals/metrics.py",
            "  用 --target 指到项目根目录",
            "  CONTRACT §1 要求六个函数都在这个文件里",
        )
    try:
        ctx = Ctx(target)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return exit_missing(f"× 导入失败：{type(exc).__name__}: {exc}")

    return run_all(
        "P2-16 判分 · 指标定义",
        CHECKS,
        ctx,
        argv=rest,
        subtitle=f"目标 {target}",
        footer=(
            "注意：这里判的是「定义对不对」。\n"
            "      卡里要的「跨模型显著性差异」要真跑两组 eval，离线判不了。\n"
            "      boot_ci 用的是全局 random，同数据两次结果会有细微差别——这是实现选择，不是错。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
