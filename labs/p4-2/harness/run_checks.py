"""P4-2 判分：三层兜底能不能真的挡住。

被判对象是 `agentlab/resilience/guards.py`，三样东西：

- `LoopGuard.check_call`  重复调用检测（按「工具名 + 参数哈希」）
- `LoopGuard.check_budget` token 预算
- `check_result_schema`    脏数据校验

判这层的意义：这三条都**不会报错**——检测失效的表现不是崩，而是「循环多跑了几轮」
「预算悄悄超了」「null 被当成答案」。所以只能靠断言压。

    python3 labs/p4-2/harness/run_checks.py --target .
"""
from __future__ import annotations

import importlib.util
import json
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
        from agentlab.resilience import guards as mod  # noqa: PLC0415

        self.mod = mod
        self.LoopGuard = mod.LoopGuard
        self.check_result_schema = mod.check_result_schema

    def guard(self):
        return self.LoopGuard()


# ---------- 1. 重复调用检测 ----------
def c1_first_two_pass(ctx: Ctx) -> str:
    g = ctx.guard()
    a = g.check_call("read_file", {"path": "a.md"})
    b = g.check_call("read_file", {"path": "a.md"})
    assert a is None and b is None, f"前两次就该放行（MAX_SAME_CALL 是「最多几次」），实际 {a!r} {b!r}"
    return "前两次都放行"


def c2_third_blocked(ctx: Ctx) -> str:
    g = ctx.guard()
    for _ in range(2):
        g.check_call("read_file", {"path": "a.md"})
    msg = g.check_call("read_file", {"path": "a.md"})
    assert msg, "第三次同工具同参数仍放行——这就是「无限循环」的入口"
    assert "read_file" in msg, f"拦截信息里没有工具名：{msg!r}"
    return f"第三次被拦：{msg[:36]}…"


def c3_different_args_ok(ctx: Ctx) -> str:
    """只按工具名去重会把「查 A」和「查 B」当成重复，误杀正常调用。"""
    g = ctx.guard()
    for path in ("a.md", "b.md", "c.md", "d.md"):
        msg = g.check_call("read_file", {"path": path})
        assert msg is None, f"换了参数还被判重复（{path}）：{msg}"
    return "四个不同参数都放行"


def c4_arg_order_irrelevant(ctx: Ctx) -> str:
    g = ctx.guard()
    g.check_call("search", {"q": "x", "k": 5})
    g.check_call("search", {"k": 5, "q": "x"})
    msg = g.check_call("search", {"q": "x", "k": 5})
    assert msg, (
        "参数字典换了个顺序就被当成不同调用——JSON 里键顺序不固定，"
        "这会让检测形同虚设（哈希前要 sort_keys）"
    )
    return "键顺序不同仍判为同一调用"


def c5_tool_scope(ctx: Ctx) -> str:
    g = ctx.guard()
    g.check_call("a", {"x": 1})
    g.check_call("a", {"x": 1})
    msg = g.check_call("b", {"x": 1})
    assert msg is None, "不同工具被算进同一个计数器（key 里少了工具名）"
    return "不同工具互不影响"


def c6_counter_is_cumulative(ctx: Ctx) -> str:
    """被拦之后继续拦，不是只拦一次。漏掉这条，模型第三次之后又会放行。"""
    g = ctx.guard()
    for _ in range(2):
        g.check_call("t", {"a": 1})
    first = g.check_call("t", {"a": 1})
    second = g.check_call("t", {"a": 1})
    assert first and second, f"只拦了第一次，第二次又放行：{second!r}"
    return "第 3、4 次都拦"


# ---------- 2. token 预算 ----------
def c7_budget_under(ctx: Ctx) -> str:
    g = ctx.guard()
    limit = ctx.mod.MAX_TOTAL_TOKENS
    msg = g.check_budget(limit // 2)
    assert msg is None, f"用了一半预算就拦：{msg}"
    return f"用 {limit // 2} / {limit} 放行"


def c8_budget_exactly_at_limit(ctx: Ctx) -> str:
    """边界写 `>` 还是 `>=`，差一个字，行为差一整轮。"""
    g = ctx.guard()
    msg = g.check_budget(ctx.mod.MAX_TOTAL_TOKENS)
    assert msg is None, f"恰好等于预算就被拦了（应为 `>` 而非 `>=`）：{msg}"
    return f"恰好用满 {ctx.mod.MAX_TOTAL_TOKENS} 放行"


def c9_budget_over(ctx: Ctx) -> str:
    g = ctx.guard()
    limit = ctx.mod.MAX_TOTAL_TOKENS
    g.check_budget(limit)
    msg = g.check_budget(1)
    assert msg, "超出 1 token 却没拦"
    assert str(limit + 1) in msg, f"拦截信息没写实际用量，看日志时不知道该不该加预算：{msg!r}"
    return f"超出后拦下并报出用量：{msg[:36]}…"


def c10_budget_is_cumulative(ctx: Ctx) -> str:
    g = ctx.guard()
    limit = ctx.mod.MAX_TOTAL_TOKENS
    for _ in range(5):
        g.check_budget(limit // 5)
    msg = g.check_budget(1)
    assert msg, "预算按单次判断而不是累计——那它就不是预算"
    return "五次各用 1/5 后，再 1 token 被拦"


# ---------- 3. 脏数据校验 ----------
def c11_missing_key(ctx: Ctx) -> str:
    ok, why = ctx.check_result_schema('{"data": null, "note": "未找到"}', ["data"])
    assert ok is False, (
        '{"data": null} 被放行了——这就是手册说的「把 null 当答案用」。'
        "缺字段和字段为 null 都算不合格"
    )
    assert "data" in why, f"理由里没说缺哪个字段：{why!r}"
    return f"拦下：{why[:36]}…"


def c12_field_none(ctx: Ctx) -> str:
    ok, _ = ctx.check_result_schema('{"data": null, "id": "x"}', ["data", "id"])
    assert ok is False, "值显式为 null 时没判不合格"
    return "null 值判不合格"


def c13_complete_dict(ctx: Ctx) -> str:
    ok, why = ctx.check_result_schema('{"data": [1,2], "id": "x"}', ["data", "id"])
    assert ok is True, f"字段齐全却被拦：{why!r}"
    return "齐全放行"


def c14_non_json_passes(ctx: Ctx) -> str:
    """非 JSON 不校验，交给模型读——这是刻意的：纯文本结果没法按 schema 判。"""
    ok, _ = ctx.check_result_schema("今天天气不错，没有结构化数据", ["data"])
    assert ok is True, "纯文本被 schema 校验拦了（它不是 JSON，没法按字段判）"
    return "纯文本放行"


def c15_bad_json_passes(ctx: Ctx) -> str:
    ok, _ = ctx.check_result_schema('{"data": ', ["data"])
    assert ok is True, "截断的 JSON 被当成「缺字段」拦了——原因判断错了，模型收到的是错误理由"
    return "截断 JSON 放行（按非 JSON 处理）"


def c16_nested_not_checked(ctx: Ctx) -> str:
    """记录边界：只查顶层。嵌套字段缺失不会被发现。"""
    ok, _ = ctx.check_result_schema('{"data": {"rows": null}}', ["data"])
    assert ok is True, "这条是记录边界，不该拦"
    return "嵌套里的 null 不查（只查顶层）"


CHECKS = [
    ("同工具同参数前两次放行", c1_first_two_pass),
    ("第三次同工具同参数被拦", c2_third_blocked),
    ("换参数不误杀", c3_different_args_ok),
    ("参数键顺序不同仍算同一调用", c4_arg_order_irrelevant),
    ("不同工具不共用一个计数器", c5_tool_scope),
    ("被拦之后继续拦（不是只拦一次）", c6_counter_is_cumulative),
    ("预算没用完不拦", c7_budget_under),
    ("恰好用满预算不拦（边界是 > 不是 >=）", c8_budget_exactly_at_limit),
    ("超预算拦下并报出实际用量", c9_budget_over),
    ("预算按累计算而不是单次", c10_budget_is_cumulative),
    ("脏数据缺字段被拦", c11_missing_key),
    ("字段值为 null 被拦", c12_field_none),
    ("字段齐全放行", c13_complete_dict),
    ("纯文本结果不按 schema 拦", c14_non_json_passes),
    ("截断的 JSON 不当成缺字段", c15_bad_json_passes),
    ("只查顶层（嵌套 null 不拦）", c16_nested_not_checked),
]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="判 P4-2 的三层兜底")
    ap.add_argument("--target", default=".", help="项目根目录（含 agentlab/）")
    args, rest = ap.parse_known_args()

    target = Path(args.target).expanduser().resolve()
    f = target / "agentlab" / "resilience" / "guards.py"
    if not f.is_file():
        return exit_missing(
            f"× 在 {target} 下没找到 agentlab/resilience/guards.py",
            "  用 --target 指到项目根目录",
            "  CONTRACT §1 要求落在这个路径",
        )
    try:
        ctx = Ctx(target)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return exit_missing(
            f"× 导入失败：{type(exc).__name__}: {exc}",
            "  CONTRACT §1 要求 agentlab.resilience.guards 提供 LoopGuard / check_result_schema / MAX_TOTAL_TOKENS",
        )

    return run_all(
        "P4-2 判分 · 三层兜底",
        CHECKS,
        ctx,
        argv=rest,
        subtitle=f"目标 {target}",
        footer=(
            "注意：这 16 条判的是「兜底逻辑本身」。\n"
            "      卡里验收还要求「五类故障下不抛未捕获异常」——那要把 guards 接进 loop 再打故障，离线判不了。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
