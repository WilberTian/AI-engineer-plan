"""P1-10 判分器：判**你的** loop.py，判据只看 CONTRACT.md。

    python3 labs/p1-10/harness/run_checks.py                 # 默认在 ./src 找 agentlab/
    python3 labs/p1-10/harness/run_checks.py --target <dir>  # 指定 src 目录

无第三方依赖（不需要 pytest）。退出码 0 = 全过。

它刻意不 import 你的 LLM 类，而是注入假 provider：
真模型每次回答不同，判据就不成立了。
"""
from __future__ import annotations

import argparse
import inspect
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "_shared"))
from checkkit import exit_missing, run_all  # noqa: E402
from fake_llm import FakeLLM, resp  # noqa: E402

PARAMS = {
    "type": "object",
    "properties": {"path": {"type": "string", "description": "相对路径"}},
    "required": ["path"],
}


class Ctx:
    """被判对象：run 以及造夹具要用的三个类。"""

    def __init__(self, run: Callable, Registry: Any, Tool: Any, ToolResult: Any):
        self.run = run
        self.Registry = Registry
        self.Tool = Tool
        self.ToolResult = ToolResult

    def tool(self, name: str = "read_file", delay: float = 0.0, size: int = 20,
             boom: bool = False, log: list | None = None):
        def _fn(path: str = "", **kw) -> Any:
            if log is not None:
                log.append(path)
            if delay:
                time.sleep(delay)
            if boom:
                raise RuntimeError("这个工具故意炸")
            return self.ToolResult(ok=True, content=f"{path}:" + "y" * size)

        return self.Tool(name=name, description="读一个文件的全部内容", parameters=PARAMS, fn=_fn)

    def reg(self, *tools) -> Any:
        r = self.Registry()
        for t in tools:
            r.register(t)
        return r


# ---------- 断言小工具 ----------

def tool_msgs(res) -> list[dict]:
    return [m for m in res.messages if isinstance(m, dict) and m.get("role") == "tool"]


def all_ids(res) -> list[str]:
    out = []
    for m in res.messages:
        if isinstance(m, dict):
            for tc in (m.get("tool_calls") or []):
                if isinstance(tc, dict) and "id" in tc:
                    out.append(tc["id"])
    return out


def assert_ids(res) -> str:
    ids = all_ids(res)
    got = [m.get("tool_call_id") for m in tool_msgs(res)]
    missing = [i for i in ids if i not in got]
    assert not missing, f"{len(ids)} 个 tool_calls 里 {len(missing)} 个没有对应 tool 消息：{missing[:3]}"
    return f"{len(ids)}/{len(ids)} 对应"


def one_tool_round(ctx: Ctx, args: str = '{"path":"notes/a.md"}', max_result_chars: int | None = None, **toolkw):
    """跑一轮工具 + 一轮结论，返回 (res, llm, tool 日志)。"""
    log: list = []
    llm = FakeLLM([
        resp(calls=[("call_1", "read_file", args)]),
        resp(content="结论：notes/a.md 里写着 x。"),
    ])
    kw = {} if max_result_chars is None else {"max_result_chars": max_result_chars}
    res = ctx.run("读 notes/a.md", llm, ctx.reg(ctx.tool(log=log, **toolkw)), **kw)
    return res, llm, log


# ---------- 14 条检查 ----------

def c1_signature(ctx: Ctx) -> str:
    sig = inspect.signature(ctx.run)
    names = set(sig.parameters)
    has_kw = any(p.kind is p.VAR_KEYWORD for p in sig.parameters.values())
    need = {"max_steps", "timeout_s", "max_result_chars"}
    if has_kw:
        return "签名里有 **kwargs，三个上限参数可由它承接"
    missing = need - names
    assert not missing, f"run() 缺少参数：{sorted(missing)}（CONTRACT 第 1 节）"
    return "三个上限参数都在签名里"


def c2_done(ctx: Ctx) -> str:
    res, _, _ = one_tool_round(ctx)
    assert res.status == "done", f"status={res.status!r}，期望 'done'"
    assert "notes/a.md 里写着 x" in (res.answer or ""), f"answer={res.answer!r}"
    return f"status=done，answer {len(res.answer)} 字"


def c3_sequence(ctx: Ctx) -> str:
    res, _, _ = one_tool_round(ctx)
    roles = [m.get("role") for m in res.messages if isinstance(m, dict)]
    assert "tool" in roles, f"messages 里没有 role=tool，实际 {roles}"
    i_tool = roles.index("tool")
    assert any(isinstance(m, dict) and m.get("tool_calls") for m in res.messages[:i_tool]), \
        "tool 消息之前没有带 tool_calls 的 assistant 消息"
    assert "assistant" in roles[i_tool + 1:], "tool 消息之后没有 assistant 消息"
    return " → ".join(roles)


def c4_ids(ctx: Ctx) -> str:
    res, _, _ = one_tool_round(ctx)
    return assert_ids(res)


def c5_backfill(ctx: Ctx) -> str:
    _, llm, _ = one_tool_round(ctx)
    assert llm.calls >= 2, f"只请求了 {llm.calls} 次，没走到第二轮"
    second = llm.requests[1]
    assert any(isinstance(m, dict) and m.get("tool_calls") for m in second), \
        "第二轮请求里没有回填第一轮带 tool_calls 的 assistant 消息（这一步漏了，真 API 会 400）"
    assert any(isinstance(m, dict) and m.get("role") == "tool" for m in second), \
        "第二轮请求里没有 role=tool 的消息"
    return f"第二轮请求 {len(second)} 条消息，含回填的 tool_calls"


def c6_max_steps(ctx: Ctx) -> str:
    script = [resp(calls=[(f"call_{i}", "read_file", '{"path":"a"}')]) for i in range(6)]
    llm = FakeLLM(script)
    res = ctx.run("永远别停", llm, ctx.reg(ctx.tool()), max_steps=3)
    assert res.status == "max_steps", f"status={res.status!r}，模型一直要工具时应为 'max_steps'"
    assert llm.calls <= 3, f"请求了 {llm.calls} 次，超过 max_steps=3"
    return f"status=max_steps，请求 {llm.calls} 次"


def c7_ids_after_stop(ctx: Ctx) -> str:
    # 每轮要两个工具、跑满 8 轮 = 16 次请求。多数实现会在这里撞上「工具预算用尽」，
    # 而预算用尽恰恰是最容易漏回 tool 消息的地方（漏一条，下一轮就 400）。
    # 没有独立预算、只靠 max_steps 兜的实现在这里不会耗尽，但下面的不变量同样必须成立。
    script = [resp(calls=[(f"call_{i}a", "read_file", '{"path":"a"}'),
                          (f"call_{i}b", "read_file", '{"path":"b"}')]) for i in range(8)]
    res = ctx.run("永远别停", FakeLLM(script), ctx.reg(ctx.tool()), max_steps=8)
    return assert_ids(res)


def c8_bad_json(ctx: Ctx) -> str:
    llm = FakeLLM([
        resp(calls=[("call_1", "read_file", '{"path": notes.md}')]),   # 少一对引号
        resp(content="好的"),
    ])
    res = ctx.run("读笔记", llm, ctx.reg(ctx.tool()))
    msgs = tool_msgs(res)
    assert msgs, "参数不是合法 JSON 时没有回灌任何 tool 消息"
    assert (msgs[0].get("content") or "").strip(), "回灌的 tool 消息是空的"
    assert res.status == "done", f"status={res.status!r}，坏参数不该让整个任务失败"
    return f"回灌 {len(msgs[0]['content'])} 字"


def c9_unknown_tool(ctx: Ctx) -> str:
    llm = FakeLLM([resp(calls=[("call_1", "write_file", "{}")]), resp(content="好的")])
    res = ctx.run("写文件", llm, ctx.reg(ctx.tool()))
    msgs = tool_msgs(res)
    assert msgs, "调了不存在的工具，没有回灌 tool 消息"
    content = msgs[0].get("content") or ""
    assert content.strip(), "回灌内容是空的"
    return content.strip().split("\n")[0][:60]


def c10_tool_raises(ctx: Ctx) -> str:
    llm = FakeLLM([
        resp(calls=[("call_1", "read_file", '{"path":"a"}')]),
        resp(content="好的"),
    ])
    res = ctx.run("读文件", llm, ctx.reg(ctx.tool(boom=True)))
    msgs = tool_msgs(res)
    assert msgs, "工具抛异常时异常逸出了 run()，或没有回灌 tool 消息"
    assert (msgs[0].get("content") or "").strip(), "回灌内容是空的"
    return "工具异常被回灌，没有逸出"


def c11_two_tools(ctx: Ctx) -> str:
    log: list = []
    llm = FakeLLM([
        resp(calls=[("call_1", "read_file", '{"path":"a"}'),
                    ("call_2", "read_file", '{"path":"b"}')]),
        resp(content="好"),
    ])
    res = ctx.run("读两个文件", llm, ctx.reg(ctx.tool(log=log)))
    assert len(log) == 2, f"一轮并调两个工具，实际只执行了 {len(log)} 次"
    assert sorted(log) == ["a", "b"], f"执行的参数不对：{log}"
    return f"两个都执行了：{log}"


def c12_timeout(ctx: Ctx) -> str:
    script = [resp(calls=[(f"call_{i}", "read_file", '{"path":"big"}')]) for i in range(6)]
    res = ctx.run("读大文件", FakeLLM(script), ctx.reg(ctx.tool(delay=0.3)),
                  max_steps=5, timeout_s=0.1)
    assert res.status == "timeout", f"status={res.status!r}，慢工具 + timeout_s=0.1 应为 'timeout'"
    return f"status=timeout，总耗时 {res.elapsed_ms:.0f}ms（预算 100ms，超了才会被拦）"


def c13_truncate(ctx: Ctx) -> str:
    res, _, _ = one_tool_round(ctx, size=5000, max_result_chars=100)
    msgs = tool_msgs(res)
    assert msgs, "没有 tool 消息"
    content = msgs[0].get("content") or ""
    assert len(content) < 5000, f"5000 字的结果没有截断（max_result_chars=100），实际 {len(content)}"
    assert len(content) <= 300, f"截断后 {len(content)} 字，超出 max_result_chars=100 太多（允许后缀，上限给到 300）"
    return f"5000 → {len(content)} 字"


def c14_elapsed(ctx: Ctx) -> str:
    res, _, _ = one_tool_round(ctx)
    assert isinstance(res.elapsed_ms, (int, float)), f"elapsed_ms 类型是 {type(res.elapsed_ms).__name__}"
    assert res.elapsed_ms > 0, f"elapsed_ms={res.elapsed_ms}"
    return f"{res.elapsed_ms:.1f}ms"


CHECKS: list[tuple[str, Callable[[Ctx], str]]] = [
    ("签名含三个上限参数", c1_signature),
    ("正常收敛：status=done", c2_done),
    ("消息序列 assistant→tool→assistant", c3_sequence),
    ("tool_call_id 逐一对应", c4_ids),
    ("assistant 消息回填到下一轮", c5_backfill),
    ("步数用尽：status=max_steps", c6_max_steps),
    ("步数用尽时 id 仍全对应", c7_ids_after_stop),
    ("参数不是合法 JSON：回灌不抛", c8_bad_json),
    ("调了不存在的工具：回灌不抛", c9_unknown_tool),
    ("工具抛异常：回灌不逸出", c10_tool_raises),
    ("一轮两个工具都真的执行", c11_two_tools),
    ("慢工具触发 timeout", c12_timeout),
    ("超长结果被截断", c13_truncate),
    ("elapsed_ms 有值", c14_elapsed),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="判 P1-10 的 loop 实现是否符合 CONTRACT.md")
    ap.add_argument("--target", default="src", help="含 agentlab/ 的目录，默认 ./src")
    args, rest = ap.parse_known_args()

    target = Path(args.target).expanduser().resolve()
    if not (target / "agentlab").is_dir():
        return exit_missing(
            f"× 在 {target} 下没找到 agentlab/",
            "  用 --target 指到你的 src 目录，例：--target ~/code/agentlab-project/src",
        )
    sys.path.insert(0, str(target))

    try:
        from agentlab.loop import run
        from agentlab.tools import Registry, Tool, ToolResult
    except Exception as exc:
        print(f"× 导入失败：{type(exc).__name__}: {exc}")
        print("  CONTRACT 第 1、4 节要求 agentlab.loop.run 和 agentlab.tools.{Registry,Tool,ToolResult} 存在")
        traceback.print_exc()
        return 2

    return run_all(
        f"P1-10 判分 · 目标 {target}",
        CHECKS,
        Ctx(run, Registry, Tool, ToolResult),
        argv=rest,
        footer=(
            "注意：全绿只说明协议层对了。卡里验收 ①③（模型选对工具、靠候选自我修正）\n"
            "      需要真模型，离线判不了——见 CONTRACT.md 第 6 节。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
