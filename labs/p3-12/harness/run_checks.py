"""P3-12 判分：上下文组装顺序与缓存命中率。

被判对象 `agentlab/context.py`：`assemble(...)` 与 `cached_ratio(usage)`。

这张卡的硬约束只有一句：**前缀只由 system + history 决定**。
把状态栏插到 system 后面，前缀每轮都变，缓存全废——而输出读起来完全正常。
所以判分器换两个不同的 state_bar，看前 N 条有没有被改动。

    python3 labs/p3-12/harness/run_checks.py --target ~/code/agentlab-project
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "_shared"))
from checkkit import exit_missing, run_all  # noqa: E402

SYS = "你是一个可以使用工具的助手，只能访问 data/ 与 notes/。"
HIST = [
    {"role": "user", "content": "先读一下 notes/todo.md"},
    {"role": "assistant", "content": "读到了：三条待办。"},
    {"role": "user", "content": "第一条是什么？"},
]
BAR_A = "## 当前状态\n目标：回答待办问题\n待办：第 1 条"
BAR_B = "## 当前状态\n目标：换个目标\n待办：第 3 条"
USER = "第一条待办讲的是什么？"


class Ctx:
    def __init__(self, target: Path):
        self.target = target
        sys.path.insert(0, str(target))
        from agentlab import context as mod  # noqa: PLC0415

        self.mod = mod
        self.assemble = mod.assemble
        self.cached_ratio = mod.cached_ratio

    def go(self, system: str = SYS, history=None, state_bar: str = BAR_A, user_text: str = USER):
        hist = HIST if history is None else history
        out = self.assemble(system, hist, state_bar, user_text)
        assert isinstance(out, list), f"assemble() 返回了 {type(out).__name__}，应为 list"
        for i, m in enumerate(out):
            assert isinstance(m, dict), f"第 {i + 1} 条消息是 {type(m).__name__}，应为 dict"
            assert "role" in m and "content" in m, f"第 {i + 1} 条消息缺 role/content：{m!r}"
        return out


# ---------- 组装 ----------
def c1_system_first(ctx: Ctx) -> str:
    out = ctx.go()
    assert out[0]["role"] == "system", f"第一条是 {out[0]['role']}，应为 system"
    assert out[0]["content"] == SYS, (
        f"第一条 system 的内容被改过：{out[0]['content'][:40]!r}…\n"
        "          往 system 里拼东西是最常见的错法——它会变成前缀的一部分"
    )
    return "system 在最前且一字不改"


def c2_history_order(ctx: Ctx) -> str:
    out = ctx.go()
    got = [m for m in out if m["role"] != "system"][:len(HIST)]
    exp = [{"role": m["role"], "content": m["content"]} for m in HIST]
    assert got == exp, (
        f"历史顺序或内容被改动了。\n          期望 {exp}\n          实际 {got}"
    )
    return f"{len(HIST)} 条历史原序保留"


def c3_user_last(ctx: Ctx) -> str:
    """最后一条必须是**本轮**提问，不只是「role 是 user」。

    这个区别很实在：历史里最后一条往往也是 user，所以只判 role 的话，
    「本轮插到历史前面」这种错法照样通过——而那会让模型去回答上一轮的问题。
    """
    out = ctx.go()
    assert out[-1]["role"] == "user", (
        f"最后一条是 {out[-1]['role']}，应为 user——"
        "本轮提问必须在最后，否则模型会以为该它继续说"
    )
    assert USER in out[-1]["content"], (
        f"最后一条 user 里没有本轮问题原文（最后一条是 {out[-1]['content'][:30]!r}…）。\n"
        "          历史里最后一条通常也是 user，只判 role 会漏掉「本轮插到历史之前」这种错法"
    )
    return "本轮提问在最后"


# ---------- 状态栏 ----------
def c4_bar_in_user(ctx: Ctx) -> str:
    out = ctx.go()
    assert BAR_A in out[-1]["content"], (
        "最后一条 user 里找不到 state_bar——状态栏没进本轮，模型看不到当前进度"
    )
    assert USER in out[-1]["content"], "最后一条 user 里找不到本轮问题原文"
    return "状态栏在本轮开头"


def c5_bar_not_in_system(ctx: Ctx) -> str:
    out = ctx.go()
    assert BAR_A not in out[0]["content"], (
        "state_bar 出现在 system 里——它每轮都变，放进 system 等于把前缀变成每轮不同，"
        "缓存命中率会恒为 0，而代码读起来完全正常"
    )
    for i, m in enumerate(out[1:], 2):
        if m["role"] == "system":
            assert BAR_A not in m["content"], f"第 {i} 条 system 里混进了 state_bar"
    return "状态栏不在 system 里"


def c6_prefix_stable(ctx: Ctx) -> str:
    """换状态栏，前 N 条必须一字不改。这是本卡的硬约束。"""
    a = ctx.go(state_bar=BAR_A)
    b = ctx.go(state_bar=BAR_B)
    n = 1 + len(HIST)
    assert len(a) >= n and len(b) >= n, f"消息条数不对：{len(a)} / {len(b)}"
    head_a, head_b = a[:n], b[:n]
    assert head_a == head_b, (
        f"换了 state_bar 之后前 {n} 条变了。\n"
        f"          前缀必须只由 system + history 决定——状态栏换一次就清一次缓存，"
        "缓存等于没开"
    )
    assert a[n:] != b[n:], "换了 state_bar 但尾部没变——状态栏没进上下文"
    return f"前 {n} 条逐字相同"


# ---------- 纯函数 ----------
def c7_history_not_mutated(ctx: Ctx) -> str:
    hist = [dict(m) for m in HIST]
    ctx.go(history=hist)
    assert hist == HIST, (
        f"传进去的 history 被改动了：\n          期望 {HIST}\n          实际 {hist}\n"
        "          改入参会让调用方下一轮拿到被污染的历史，而且很难查"
    )
    return "入参未被修改"


def c8_returns_new_list(ctx: Ctx) -> str:
    hist = [dict(m) for m in HIST]
    out = ctx.go(history=hist)
    assert out is not hist, "返回的就是传进来的 history 对象本身——调用方 append 会直接改到它"
    return "返回新列表"


# ---------- 边界 ----------
def c9_empty_history(ctx: Ctx) -> str:
    out = ctx.go(history=[])
    assert len(out) == 2, (
        f"空历史时应该有 2 条（system + 本轮），实际 {len(out)} 条："
        f"{[m['role'] for m in out]}"
    )
    return "空历史 → 2 条"


def c10_roles_valid(ctx: Ctx) -> str:
    out = ctx.go()
    ok = {"system", "user", "assistant", "tool"}
    bad = [m["role"] for m in out if m["role"] not in ok]
    assert not bad, f"出现非法 role：{bad}"
    empty = [m["role"] for m in out if not str(m.get("content", "")).strip()]
    assert not empty, f"有 {len(empty)} 条消息 content 是空的——空消息会被供应商直接拒"
    return f"{len(out)} 条消息 role 都合法"


# ---------- 命中率 ----------
def _usage(hit=0, total=0, with_details=True):
    details = SimpleNamespace(cached_tokens=hit) if with_details else None
    return SimpleNamespace(prompt_tokens=total, prompt_tokens_details=details)


def c11_ratio_basic(ctx: Ctx) -> str:
    r = ctx.cached_ratio(_usage(hit=50, total=200))
    assert abs(r - 0.25) < 1e-9, f"50/200 应得 0.25，实际 {r!r}"
    return "50/200 → 0.25"


def c12_ratio_no_details(ctx: Ctx) -> str:
    r = ctx.cached_ratio(_usage(hit=0, total=800, with_details=False))
    assert r == 0, f"没有缓存字段时应为 0，实际 {r!r}——顺手把它当成「全部命中」很危险"
    return "无缓存字段 → 0"


def c13_ratio_zero_total(ctx: Ctx) -> str:
    """第一轮常常没有 prompt_tokens 统计，除零会让整个请求崩在记账那一行。"""
    r = ctx.cached_ratio(_usage(hit=0, total=0))
    assert r == 0, f"total=0 时应返回 0（不除零），实际 {r!r}"
    return "total=0 → 0"


def c14_ratio_none(ctx: Ctx) -> str:
    r = ctx.cached_ratio(None)
    assert r == 0, f"usage 为 None 时应返回 0，实际 {r!r}——第一轮拿不到 usage 是常态"
    return "usage=None → 0"


# ---------- 状态栏模板 ----------
def c15_state_bar_sane(ctx: Ctx) -> str:
    bar = getattr(ctx.mod, "STATE_BAR", "")
    assert isinstance(bar, str) and bar.strip(), "模块里没有 STATE_BAR"
    assert "{" in bar, "STATE_BAR 没有占位符——那它就不是模板，是写死的内容"
    for slot in ("目标", "待办"):
        assert slot in bar, f"STATE_BAR 缺槽位「{slot}」——状态栏要能回答「在做什么、还差什么」"
    assert len(bar) <= 300, (
        f"STATE_BAR 有 {len(bar)} 字符（建议 ≤300）。状态栏每轮都要重发，"
        "它自己变成一段长文就本末倒置了"
    )
    return f"{len(bar)} 字符，槽位齐全"


CHECKS = [
    ("system 在最前且一字不改", c1_system_first),
    ("历史原序保留", c2_history_order),
    ("本轮提问在最后", c3_user_last),
    ("状态栏在本轮开头", c4_bar_in_user),
    ("状态栏不在 system 里", c5_bar_not_in_system),
    ("换状态栏前缀不变", c6_prefix_stable),
    ("入参历史未被修改", c7_history_not_mutated),
    ("返回新列表", c8_returns_new_list),
    ("空历史只剩 2 条", c9_empty_history),
    ("消息 role 都合法", c10_roles_valid),
    ("命中率 50/200=0.25", c11_ratio_basic),
    ("无缓存字段算 0", c12_ratio_no_details),
    ("total=0 不除零", c13_ratio_zero_total),
    ("usage 为 None 算 0", c14_ratio_none),
    ("状态栏模板合理", c15_state_bar_sane),
]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="判 P3-12 的上下文组装")
    ap.add_argument("--target", default=".", help="项目根目录（含 agentlab/）")
    args, rest = ap.parse_known_args()

    target = Path(args.target).expanduser().resolve()
    if not (target / "agentlab" / "context.py").is_file():
        return exit_missing(
            f"× 在 {target} 下没找到 agentlab/context.py",
            "  用 --target 指到项目根目录",
            "  CONTRACT §1 要求 assemble() / cached_ratio() / STATE_BAR 在这里",
        )
    try:
        ctx = Ctx(target)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return exit_missing(f"× 导入失败：{type(exc).__name__}: {exc}")

    return run_all(
        "P3-12 判分 · 上下文组装",
        CHECKS,
        ctx,
        argv=rest,
        subtitle=f"目标 {target}",
        footer=(
            "注意：这里判「前缀稳定」这个必要条件，判不了「命中率到底多少」。\n"
            "      真实命中率要发两次请求看 cached_tokens——但前缀不稳，那个数必然是 0。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
