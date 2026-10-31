"""P1-9 判分器：判**你的** tools.py 是否符合 CONTRACT.md。

    python3 labs/p1-9/harness/run_checks.py                 # 默认在 ./src 找 agentlab/
    python3 labs/p1-9/harness/run_checks.py --target <dir>  # 指定 src 目录

无第三方依赖（不需要 pytest）。退出码 0 = 全过。

判分前会 chdir 到一个临时工作目录，里面已备好 data/notes/ 的两份笔记：
工具按 CWD 解析相对路径，不换目录就没法验证「同目录候选」那条。
"""
from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "_shared"))
from checkkit import exit_missing, run_all  # noqa: E402

# 夹具：笔记正文。同时放到 data/notes/ 与 notes/ 两处——
# 手册里 NOTES_DIR 写的是 data/notes，而 read_file 的例子写的是 notes/todo.md，
# 两种约定都在用。判错一个目录名毫无教学价值，所以两处都备好（见 NOTES §4）。
NOTE_BODY = {
    "todo.md": "# 待办\n- 周五前把 eval 跑通\n- 补充 judge 的一致性检验\n",
    "loop.md": "# loop 笔记\n三个停止条件：模型给结论、步数用尽、超时。\n",
    "deep/nested.md": "嵌套目录里的文件，用来验证 rglob。\n",
}


class Ctx:
    """被判对象：模块级三个工具 + Registry / Tool / ToolResult / build_registry。"""

    def __init__(self, mod: Any, workdir: Path):
        self.mod = mod
        self.Registry = mod.Registry
        self.Tool = mod.Tool
        self.ToolResult = mod.ToolResult
        self.build_registry = mod.build_registry
        self.workdir = workdir

    def call(self, name: str, **kwargs):
        """直接调模块级工具函数，不经过模型，也不碰 Registry 的私有结构。"""
        fn = getattr(self.mod, name, None)
        assert fn is not None, f"agentlab.tools 里没有模块级函数 {name}（CONTRACT §1）"
        return fn(**kwargs)


# ---------- 检查 ----------

def c1_shape(ctx: Ctx) -> str:
    import dataclasses

    for cls, fields in ((ctx.Tool, ("name", "description", "parameters", "fn")),
                        (ctx.ToolResult, ("ok", "content"))):
        assert dataclasses.is_dataclass(cls), f"{cls.__name__} 不是 dataclass（CONTRACT §1）"
        have = {f.name for f in dataclasses.fields(cls)}
        missing = set(fields) - have
        assert not missing, f"{cls.__name__} 缺字段 {sorted(missing)}，实际 {sorted(have)}"
    return "Tool / ToolResult 字段齐"


def c2_register(ctx: Ctx) -> str:
    r = ctx.Registry()
    r.register(ctx.Tool(name="t1", description="d", parameters={"type": "object"}, fn=lambda: None))
    assert r.names() == ["t1"], f"names() 返回 {r.names()}"
    return "注册 + names() 正常"


def c3_dup(ctx: Ctx) -> str:
    r = ctx.Registry()
    tool = ctx.Tool(name="dup", description="d", parameters={"type": "object"}, fn=lambda: None)
    r.register(tool)
    try:
        r.register(ctx.Tool(name="dup", description="d2", parameters={"type": "object"}, fn=lambda: None))
    except ValueError:
        return "重名当场报错（不是静默覆盖）"
    raise AssertionError("重名注册被静默接受——模型「总是调错工具」的头号来源（CONTRACT §2）")


def c4_spec_shape(ctx: Ctx) -> str:
    r = ctx.build_registry()
    specs = r.specs()
    assert specs, "specs() 是空的"
    s = specs[0]
    assert s.get("type") == "function", f"spec.type={s.get('type')!r}，OpenAI 兼容协议要求 'function'"
    fn = s.get("function") or {}
    for k in ("name", "description", "parameters"):
        assert k in fn, f"spec.function 缺 {k}，实际键 {sorted(fn)}"
    assert isinstance(fn["parameters"], dict), f"parameters 类型是 {type(fn['parameters']).__name__}"
    return f"{len(specs)} 个 spec，形状正确"


def c5_descriptions(ctx: Ctx) -> str:
    r = ctx.build_registry()
    bad = [s["function"]["name"] for s in r.specs()
           if len((s["function"].get("description") or "").strip()) < 10]
    assert not bad, f"这些工具的 description 太短（模型只看这句决定调不调）：{bad}"
    return "三个工具的 description 都写了「什么时候用」"


def c6_three_tools(ctx: Ctx) -> str:
    names = set(ctx.build_registry().names())
    need = {"search_notes", "fetch_url", "read_file"}
    missing = need - names
    assert not missing, f"build_registry() 少了 {sorted(missing)}，实际 {sorted(names)}"
    return f"{sorted(names)}"


def c7_read_existing(ctx: Ctx) -> str:
    r = ctx.call("read_file", path="notes/todo.md")
    assert r.ok, f"读存在的文件返回 ok=False：{r.content[:80]!r}"
    assert "eval" in r.content, f"内容不含文件正文：{r.content[:80]!r}"
    return f"读到 {len(r.content)} 字"


def c8_abs_path(ctx: Ctx) -> str:
    r = ctx.call("read_file", path="/etc/passwd")
    assert not r.ok, "绝对路径被放行了（越权）。CONTRACT §3 要求只接受相对路径"
    return r.content[:50]


def c9_dotdot(ctx: Ctx) -> str:
    """上级目录放一个真实文件，让「被沙箱拦住」和「文件本来就不存在」可区分。

    只测 ../不存在.md 是不够的：删掉那道闸之后它照样 ok=False（因为找不到文件），
    断言会变成永远通过——判分器体检抓出过这个洞。
    """
    outside = ctx.workdir.parent / f"secret-{ctx.workdir.name}.md"
    outside.write_text("SECRET-CONTENT", encoding="utf-8")
    try:
        r = ctx.call("read_file", path=f"../{outside.name}")
        assert not r.ok, f"`..` 上跳读到了工作目录外的文件（越权）：{r.content[:60]!r}"
        assert "SECRET-CONTENT" not in r.content, "越权读到了上级目录的文件正文"
        return r.content[:50]
    finally:
        outside.unlink(missing_ok=True)


def c10_candidates(ctx: Ctx) -> str:
    """卡里验收的核心：报错时要给出同目录候选，模型下一次才改得对。"""
    r = ctx.call("read_file", path="notes/不存在.md")
    assert not r.ok, "读不存在的文件返回了 ok=True"
    for cand in ("todo.md", "loop.md"):
        assert cand in r.content, (
            f"报错信息里没有同目录候选 {cand}。实际：{r.content[:120]!r}\n"
            "         模型看不到候选就只能瞎猜路径，这一条是 p1-11 实验 A 的前提"
        )
    return "候选含 todo.md / loop.md"


def c11_missing_dir(ctx: Ctx) -> str:
    r = ctx.call("read_file", path="nowhere/x.md")
    assert not r.ok, "读不存在的目录返回了 ok=True"
    assert r.content.strip(), "不存在的目录返回了空内容，模型什么也拿不到"
    return "目录不存在时仍返回可读信息，没有抛异常"


def c12_search_hit(ctx: Ctx) -> str:
    r = ctx.call("search_notes", query="停止条件")
    assert r.ok, f"命中时返回 ok=False：{r.content[:80]!r}"
    assert "loop.md" in r.content, f"命中结果里没有文件名，模型不知道去哪读：{r.content[:120]!r}"
    return r.content.replace("\n", " ")[:60]


def c13_search_miss(ctx: Ctx) -> str:
    r = ctx.call("search_notes", query="绝对不存在的词xyzzy")
    assert r.ok, "没搜到结果时返回 ok=False——这不是错误，是正常的空结果"
    assert r.content.strip(), "没搜到时返回空字符串，模型不知道发生了什么"
    return r.content[:60]


def c14_fetch_scheme(ctx: Ctx) -> str:
    """必须在**发请求之前**拒绝，而不是让 http 库报「不支持该协议」。

    两者对模型是两回事：前者能说清「该给 http 链接」，后者只说「抓取失败」。
    所以这里看的不只是 ok=False（那是必要条件），还要看拒绝理由提到协议。
    """
    r = ctx.call("fetch_url", url="file:///etc/passwd")
    assert not r.ok, "file:// 协议被放行了"
    # 断言用 "http://" 而不是 "http"：环境里没装 httpx 时错误信息是
    # "No module named 'httpx'"，用 "http" 会被这个词误命中（判分器体检抓出来的）。
    assert "http://" in r.content, (
        f"拒绝理由没提协议限制：{r.content[:80]!r}\n"
        "         应当在调用 http 库之前就拒绝，否则模型收到的是「抓取失败」而不是「该给 http 链接」"
    )
    r2 = ctx.call("fetch_url", url="example.com")
    assert not r2.ok, "不带协议的 url 被放行了"
    return "非 http/https 都被拒，且理由说明协议要求"


CHECKS = [
    ("Tool/ToolResult 字段齐", c1_shape),
    ("Registry 注册与 names()", c2_register),
    ("重名注册当场报错", c3_dup),
    ("specs() 是 OpenAI 兼容形状", c4_spec_shape),
    ("每个工具的 description 够用", c5_descriptions),
    ("build_registry() 有三个工具", c6_three_tools),
    ("read_file 能读存在的文件", c7_read_existing),
    ("read_file 拒绝绝对路径", c8_abs_path),
    ("read_file 拒绝 .. 上跳", c9_dotdot),
    ("read_file 报错时给同目录候选", c10_candidates),
    ("目录不存在也不抛异常", c11_missing_dir),
    ("search_notes 命中带文件名", c12_search_hit),
    ("search_notes 没命中是 ok=True", c13_search_miss),
    ("fetch_url 只接受 http/https", c14_fetch_scheme),
]


def prepare_workdir() -> Path:
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="p1-9-lab-"))
    for root in ("data/notes", "notes"):
        for rel, text in NOTE_BODY.items():
            p = tmp / root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
    return tmp


def main() -> int:
    ap = argparse.ArgumentParser(description="判 P1-9 的 tools.py 是否符合 CONTRACT.md")
    ap.add_argument("--target", default="src", help="含 agentlab/ 的目录，默认 ./src")
    args, rest = ap.parse_known_args()

    target = Path(args.target).expanduser().resolve()
    if not (target / "agentlab").is_dir():
        return exit_missing(
            f"× 在 {target} 下没找到 agentlab/",
            "  用 --target 指到你的 src 目录，例：--target ~/code/agentlab-project/src",
        )

    workdir = prepare_workdir()
    os.chdir(workdir)                      # 工具用 CWD 解析 data/notes 与相对路径
    sys.path.insert(0, str(target))

    try:
        from agentlab import tools as mod
    except Exception as exc:
        print(f"× 导入失败：{type(exc).__name__}: {exc}")
        print("  CONTRACT §1 要求 agentlab.tools 提供 Registry / Tool / ToolResult / build_registry")
        traceback.print_exc()
        return 2

    return run_all(
        f"P1-9 判分 · 目标 {target}",
        CHECKS,
        Ctx(mod, workdir),
        argv=rest,
        subtitle="所有检查都在临时目录里跑（data/notes/ 已备好），不碰你的项目文件",
        footer=(
            "注意：全绿说明工具层的边界和报错信息对了。\n"
            "      卡里验收「三个工具单独都能跑通」里的 fetch_url 真联网那条判不了，见 CONTRACT §5。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
