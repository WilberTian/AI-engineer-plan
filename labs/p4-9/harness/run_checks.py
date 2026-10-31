"""P4-9 判分：路由规则分得对不对。

被判对象 `agentlab/routing.py`：`route(task, history_len, has_tools) -> Route`。

判的是**分类边界**，不是分类质量——「这个任务该不该用大模型」需要真跑 eval 才知道，
但你至少得先保证：三档都能走到、边界是清晰的、难度信号不会被前面的规则吃掉。

    python3 labs/p4-9/harness/run_checks.py --target ~/code/agentlab-project
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
        from agentlab import routing as mod  # noqa: PLC0415

        self.mod = mod
        self.route = mod.route
        self.Route = mod.Route

    def go(self, task: str, history_len: int = 0, has_tools: bool = False):
        r = self.route(task, history_len, has_tools)
        assert isinstance(r, self.Route), f"route() 返回了 {type(r).__name__}，不是 Route"
        return r


# ---------- 三档都可达 ----------
def c1_simple(ctx: Ctx) -> str:
    r = ctx.go("今天几号")
    assert r.name == "simple", f"「今天几号」被判成 {r.name}——最短路径没生效"
    return f"simple → {r.model}"


# 用例长度都 >40 字：短用例测出来的往往是「长度规则」，不是「难度信号」
LONG_HARD = "为什么这个方案在长文档上的召回率一直上不去，帮我分析一下可能的原因，并证明你的结论是有证据支撑的"
LONG_PLAIN = "请阅读我贴的这份材料，把里面的关键结论按重要性排序整理成一份列表，每条后面注明它出现在原文的第几段"


def c2_hard(ctx: Ctx) -> str:
    assert len(LONG_HARD) > 40, "用例写短了，这条测不出难度标记"
    r = ctx.go(LONG_HARD, history_len=0)
    assert r.name == "hard", f"含「分析/为什么/证明」的长问被判成 {r.name}"
    return f"hard → {r.model}"


def c3_default(ctx: Ctx) -> str:
    assert len(LONG_PLAIN) > 40, "用例写短了，会落进 simple"
    r = ctx.go(LONG_PLAIN, history_len=0, has_tools=False)
    assert r.name == "default", f"超过 40 字、无难度标记的常规任务被判成 {r.name}"
    return f"default → {r.model}"


def c4_three_models_differ(ctx: Ctx) -> str:
    """三档用同一个模型 = 路由没意义（成本一分没省）。"""
    m = {ctx.go("今天几号").model, ctx.go(LONG_HARD, 0).model, ctx.go(LONG_PLAIN, 0).model}
    assert len(m) >= 3, f"三档只用了 {len(m)} 个模型（{m}）——至少有一档没换模型"
    return f"三档共 {len(m)} 个模型"


# ---------- simple 的边界 ----------
def c5_simple_requires_no_tools(ctx: Ctx) -> str:
    r = ctx.go("今天几号", has_tools=True)
    assert r.name != "simple", "带工具的短问题被判 simple——工具场景一轮就要重发全部上下文，小模型扛不住"
    return f"带工具 → {r.name}"


def c6_simple_requires_no_history(ctx: Ctx) -> str:
    r = ctx.go("今天几号", history_len=1)
    assert r.name != "simple", "有历史还被判 simple——历史越长越需要判断力"
    return f"有历史 → {r.name}"


def c7_simple_length_boundary(ctx: Ctx) -> str:
    """39 字 vs 41 字，落在边界两侧就该分到不同档（或至少不都 simple）。"""
    short = ctx.go("帮我" + "看" * 20)              # 22 字
    long = ctx.go("帮我看" + "一下这段材料" * 8)     # 长
    assert short.name != long.name or short.name != "simple", (
        f"22 字与 {len(long)} 字被判成同一档 {short.name}——长度阈值没起作用"
    )
    return f"短={short.name} 长={long.name}"


# ---------- hard 的信号 ----------
def c8_marker_beats_default(ctx: Ctx) -> str:
    """难度标记要压过「默认档」，用长用例测，避免被长度规则干扰。"""
    tail = "这段代码在不同输入下的行为是否保持一致，并给出你的判断依据和完整的理由说明"
    for kw in ("分析", "对比", "为什么", "设计", "重构", "debug", "证明"):
        task = f"请{kw}{tail}"
        assert len(task) >= 40, f"用例「{kw}」写短了（{len(task)} 字，simple 的门槛是 <40）"
        r = ctx.go(task, history_len=0)
        assert r.name == "hard", f"含「{kw}」的任务被判成 {r.name}"
    return "七个难度标记都升到 hard"


def c9_marker_beats_simple(ctx: Ctx) -> str:
    """难度标记必须**先于**「短问题」规则判断，否则短而难的任务全被降到小模型。

    这是路由里最常见的一类错：规则按「便宜的判断在前」写，结果难度信号被前面的
    长度规则吃掉了。实测参考实现就是这条红。
    """
    r = ctx.go("设计一个分块策略")            # 8 字，无工具无历史
    assert r.name == "hard", (
        f"「{r.name}」——8 个字但有「设计」，被判成了 {r.name}。\n"
        "          短不等于简单：短而难的问题（设计/证明/为什么）降到小模型，\n"
        "          代价是一次答错要重来，比省下的那点钱贵得多"
    )
    return "短但含难度标记 → hard"


def c10_long_history_is_hard(ctx: Ctx) -> str:
    r = ctx.go("继续", history_len=11)
    assert r.name == "hard", f"11 轮历史被判 {r.name}——长上下文该升级"
    return f"11 轮历史 → {r.name}"


def c11_history_boundary(ctx: Ctx) -> str:
    """边界定在 10/11 之间（手册写的是 `history_len > 10`），不是 9/10 也不是 11/12。

    为什么这条要严格：边界挪一格不报错，只是「10 轮对话」这一类任务被静默降级或升级，
    成本和质量都会偏，而你看不出来。
    """
    a = ctx.go("继续", history_len=10)
    b = ctx.go("继续", history_len=11)
    assert a.name != "hard", f"10 轮历史被判成 hard——门槛应是 >10，边界挪了一格（实际 {a.name}）"
    assert b.name == "hard", f"11 轮历史被判成 {b.name}——门槛应是 >10"
    return f"10 轮={a.name} 11 轮={b.name}"


# ---------- 可解释与纯函数 ----------
def c12_reason_not_empty(ctx: Ctx) -> str:
    for task, h, t in [("今天几号", 0, False), ("为什么不行", 0, False), ("整理成列表", 0, False)]:
        r = ctx.go(task, h, t)
        assert r.reason and len(r.reason) >= 4, f"{r.name} 档的 reason 太空：{r.reason!r}"
    return "三档都给了理由"


def c13_pure(ctx: Ctx) -> str:
    seq = [(ctx.go("今天几号").name, ctx.go("今天几号").model) for _ in range(3)]
    assert len(set(seq)) == 1, f"同一输入三次路由结果不同：{seq}"
    return "同一输入结果稳定"


def c14_no_dead_route(ctx: Ctx) -> str:
    """每个档位名至少被走到一次，否则就是死分支。"""
    seen = set()
    for task, h, t in [
        ("今天几号", 0, False),
        ("为什么这个不行，帮我分析证明", 0, False),
        ("把这段整理成要点", 0, False),
        ("继续", 11, False),
        ("看下这个文件", 0, True),
    ]:
        seen.add(ctx.go(task, h, t).name)
    assert "simple" in seen, f"simple 档走不到（实际走到 {seen}）"
    assert "hard" in seen, f"hard 档走不到（实际走到 {seen}）"
    return f"覆盖档位 {sorted(seen)}"


CHECKS = [
    ("短问题走 simple", c1_simple),
    ("含难度标记走 hard", c2_hard),
    ("常规问题走 default", c3_default),
    ("三档至少用两个模型", c4_three_models_differ),
    ("带工具不判 simple", c5_simple_requires_no_tools),
    ("有历史不判 simple", c6_simple_requires_no_history),
    ("长度阈值真的起作用", c7_simple_length_boundary),
    ("七个难度标记都升到 hard", c8_marker_beats_default),
    ("短但含难度标记仍判 hard", c9_marker_beats_simple),
    ("长历史升级到 hard", c10_long_history_is_hard),
    ("历史边界落在 10/11 之间", c11_history_boundary),
    ("每档都有非空理由", c12_reason_not_empty),
    ("同一输入结果稳定", c13_pure),
    ("没有走不到的档位", c14_no_dead_route),
]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="判 P4-9 的模型路由")
    ap.add_argument("--target", default=".", help="项目根目录（含 agentlab/）")
    args, rest = ap.parse_known_args()

    target = Path(args.target).expanduser().resolve()
    if not (target / "agentlab" / "routing.py").is_file():
        return exit_missing(
            f"× 在 {target} 下没找到 agentlab/routing.py",
            "  用 --target 指到项目根目录",
            "  CONTRACT §1 要求 route() 与 Route 在这里",
        )
    try:
        ctx = Ctx(target)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return exit_missing(f"× 导入失败：{type(exc).__name__}: {exc}")

    return run_all(
        "P4-9 判分 · 模型路由",
        CHECKS,
        ctx,
        argv=rest,
        subtitle=f"目标 {target}",
        footer=(
            "注意：这里判的是「分类边界」。\n"
            "      卡里验收要求「成本降 ≥30%、通过率掉 ≤2 点、每档掉点 ≤5」——那必须真跑 eval 的两组对照，离线判不了。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
