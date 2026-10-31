"""P4-1 判分：故障注入框架能不能「一开关就换一副样子」。

被判对象是 `agentlab/resilience/faults.py`。判分只看三件事：

1. 关掉时是不是**完全**没影响（不是「大致没影响」）
2. 每种故障打开后，注入的是不是**那一类**故障（别把 dirty 注入成 exception）
3. 同样的配置跑两次，结果一不一样（可复现才谈得上排查）

第 3 条容易被当成小事，其实它决定了「故障能不能复现」——不能复现的故障，
你只能在客户那边看运气。

    python3 labs/p4-1/harness/run_checks.py --target ~/code/agentlab-project
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "_shared"))
from checkkit import exit_missing, run_all  # noqa: E402

ALL_FAULTS = ("slow", "timeout", "dirty", "exception", "empty")


class Ctx:
    """按需重新加载被判模块。每次改 FAULTS 都必须重新导入——SPEC 是模块级常量。"""

    def __init__(self, target: Path):
        self.target = target
        self.modpath = target / "agentlab" / "resilience" / "faults.py"
        self.ToolResult = self._import_toolresult()

    def _import_toolresult(self):
        sys.path.insert(0, str(self.target))
        from agentlab.tools import ToolResult  # noqa: PLC0415

        return ToolResult

    def ok(self, content: str = "正常内容"):
        return self.ToolResult(ok=True, content=content)

    def load(self, faults: str = "", *, name: str = "faults_under_test"):
        """把 FAULTS 设成 faults 后重新加载模块，返回模块对象。"""
        os.environ["FAULTS"] = faults
        # 清掉上一轮的模块与 agentlab 缓存，否则拿到的是旧 SPEC
        for m in [k for k in sys.modules if k == name]:
            del sys.modules[m]
        spec = importlib.util.spec_from_file_location(name, self.modpath)
        if spec is None or spec.loader is None:
            raise AssertionError(f"加载不了 {self.modpath}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod            # dataclass 需要先注册再 exec
        spec.loader.exec_module(mod)
        return mod


# ---------- 1. 关掉时零影响 ----------
def c1_off_identity(ctx: Ctx) -> str:
    mod = ctx.load("")
    r = ctx.ok("原文")
    for name in ("read_file", "search_notes", "fetch_url"):
        got = mod.maybe_fault(name, r)
        assert got is r, f"FAULTS 为空时 {name} 的结果不是原对象（返回了 {got!r}），说明关闭状态下仍在加工"
    return "三种工具名都原样透传（同一对象）"


def c2_off_spec_disabled(ctx: Ctx) -> str:
    mod = ctx.load("")
    assert mod.SPEC.enabled is False, f"FAULTS 为空时 SPEC.enabled 应为 False，实为 {mod.SPEC.enabled}"
    mod2 = ctx.load("slow=0")
    assert mod2.SPEC.enabled is False, "slow=0 被当成了「开启」（0.0 应视同关闭）"
    return "空配置与全 0 配置都是 enabled=False"


def c3_unknown_key_ignored(ctx: Ctx) -> str:
    """写错一个键名不该让整个进程起不来——但也不能悄悄生效。"""
    try:
        mod = ctx.load("nonsense=1.0")
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(
            f"未知键导致加载失败：{type(exc).__name__}: {exc}\n"
            "          环境变量是手敲的，写错一个键就崩会让人不敢用"
        ) from exc
    assert mod.SPEC.enabled is False, "未知键竟被当成了有效配置"
    return "未知键被忽略，且没有生效"


def c4_unknown_mixed(ctx: Ctx) -> str:
    mod = ctx.load("nonsense=1.0,exception=1.0")
    assert mod.SPEC.enabled is True, "未知键把已知键一起吃掉了"
    assert mod.SPEC.exception == 1.0, f"exception 没解析出来：{mod.SPEC.exception}"
    return "未知键与已知键混写时，已知的仍然生效"


# ---------- 2. 每类故障注入的是不是那一类 ----------
def c5_exception(ctx: Ctx) -> str:
    mod = ctx.load("exception=1.0")
    try:
        mod.maybe_fault("read_file", ctx.ok())
    except RuntimeError as exc:
        assert "read_file" in str(exc), f"异常信息里没有工具名，排查时不知道是哪个工具：{exc}"
        return f"抛 RuntimeError 且带工具名：{str(exc)[:40]}"
    raise AssertionError("exception=1.0 却没有抛异常")


def c6_timeout(ctx: Ctx) -> str:
    mod = ctx.load("timeout=1.0")
    got = mod.maybe_fault("fetch_url", ctx.ok())
    assert got.ok is False, "超时应当 ok=False，实际 ok=True"
    assert "fetch_url" in got.content, f"超时信息里没有工具名：{got.content[:60]!r}"
    return "ok=False 且消息带工具名"


def c7_dirty_is_not_original(ctx: Ctx) -> str:
    mod = ctx.load("dirty=1.0")
    orig = ctx.ok("真实的搜索结果：第 3 页第 2 段")
    got = mod.maybe_fault("search_notes", orig)
    assert got.ok is True, "脏数据是「合法但错」，不该标成 ok=False（标成 False 就退化成了超时那类）"
    assert got.content != orig.content, "dirty=1.0 返回了原文，等于没注入"
    try:
        json.loads(got.content)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"脏数据应当是合法 JSON（错的不是格式而是内容）：{got.content[:80]!r}") from exc
    return f"ok=True 且内容被换成合法但不同的 JSON：{got.content[:38]}…"


def c8_empty(ctx: Ctx) -> str:
    mod = ctx.load("empty=1.0")
    got = mod.maybe_fault("read_file", ctx.ok("有内容"))
    assert got.content == "", f"empty=1.0 应返回空串，实为 {got.content[:40]!r}"
    return "返回空串（工具成功但没找到东西，最常见的一类）"


def c9_slow(ctx: Ctx) -> str:
    """slow 走的是「真的变慢」，不是返回错误。用替身捕睡，不真等 3 秒。"""
    mod = ctx.load("slow=1.0")
    slept: list[float] = []
    real = time.sleep
    time.sleep = lambda s: slept.append(s)  # type: ignore[assignment]
    try:
        r = ctx.ok("慢但正确")
        got = mod.maybe_fault("read_file", r)
    finally:
        time.sleep = real  # type: ignore[assignment]
    assert slept, "slow=1.0 没有调用 sleep，说明「变慢」没实现（或实现成了返回错误）"
    assert got.content == r.content, "slow 应当返回**正常结果**，只是慢了；返回错误就变成了超时那类"
    return f"sleep({slept[0]}s) 后返回原结果"


def c10_all_are_toolresult(ctx: Ctx) -> str:
    for env in ("timeout=1.0", "dirty=1.0", "empty=1.0"):
        mod = ctx.load(env)
        got = mod.maybe_fault("read_file", ctx.ok())
        assert isinstance(got, ctx.ToolResult), f"{env} 的返回值不是 ToolResult：{type(got).__name__}"
    return "三种「返回结果」的故障都返回 ToolResult，不是裸字符串"


# ---------- 3. 可复现与顺序 ----------
def c11_reproducible(ctx: Ctx) -> str:
    """比 ok 没用：dirty 是 ok=True，正常结果也是 ok=True，两边一样就永远相等。比内容。"""
    seqs = []
    for _ in range(2):
        mod = ctx.load("dirty=0.5")
        seqs.append([mod.maybe_fault("t", ctx.ok("基线")).content for _ in range(20)])
    assert seqs[0] == seqs[1], (
        f"两次加载同一配置，故障序列不同：\n          第一次 {seqs[0]}\n          第二次 {seqs[1]}\n"
        "          不确定的故障没法复现，也没法写进回归测试"
    )
    hits = sum(1 for c in seqs[0] if c != "基线")
    assert 0 < hits < 20, (
        f"dirty=0.5 的 20 次里命中 {hits} 次——全是或全不是，说明概率没起作用"
        "（注意：五种故障各抽一次随机数，dirty 是第三次抽，命中率仍应是 50% 左右）"
    )
    return f"20 次内容序列一致，命中 {hits} 次"


def c12_short_circuit_order(ctx: Ctx) -> str:
    """两种故障都开 1.0 时，走哪条由代码顺序决定，不是随机分派。

    这条断言的是**记录事实**：确认顺序固定，从而「近似相加」的概率估算成立。
    """
    mod = ctx.load("timeout=1.0,exception=1.0")
    kinds = []
    for _ in range(5):
        try:
            r = mod.maybe_fault("t", ctx.ok())
            kinds.append("ok" if r.ok and r.content == "基线" else "fault")
        except RuntimeError:
            kinds.append("exception")
    assert kinds.count("exception") == 0, (
        f"timeout 与 exception 都开 1.0 时出现了 exception（{kinds}）——"
        "说明分派是随机的，那「总故障率约等于相加」的估算就不成立了"
    )
    return f"前一项恒定短路后一项：{kinds}"


def c13_bad_value_fails_loud(ctx: Ctx) -> str:
    """配置写错（slow=abc）必须当场报出来，不能静默当成关闭。"""
    try:
        ctx.load("slow=abc")
    except ValueError:
        return "非法数值当场 ValueError（fail fast）"
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"抛的是 {type(exc).__name__} 而不是 ValueError：{exc}") from exc
    raise AssertionError(
        "slow=abc 既没报错也没生效——最坏的一种：你以为开着故障在测，其实一直在跑正常模式"
    )


CHECKS = [
    ("FAULTS 为空时原样透传（同一对象）", c1_off_identity),
    ("空配置与全 0 配置都算关闭", c2_off_spec_disabled),
    ("未知键被忽略而不是让进程起不来", c3_unknown_key_ignored),
    ("未知键与已知键混写时已知的仍生效", c4_unknown_mixed),
    ("exception 注入抛异常且带工具名", c5_exception),
    ("timeout 注入 ok=False 且带工具名", c6_timeout),
    ("dirty 注入是「合法但错」而不是「返回失败」", c7_dirty_is_not_original),
    ("empty 注入返回空串", c8_empty),
    ("slow 注入是真变慢且仍返回正确结果", c9_slow),
    ("三种故障的返回值都是 ToolResult", c10_all_are_toolresult),
    ("同一配置两次加载的故障序列一致", c11_reproducible),
    ("多故障同开时短路顺序固定", c12_short_circuit_order),
    ("非法配置值当场报错而不是静默关闭", c13_bad_value_fails_loud),
]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="判 P4-1 的故障注入框架")
    ap.add_argument("--target", default=".", help="项目根目录（含 agentlab/）")
    args, rest = ap.parse_known_args()      # 其余参数原样透传给 --filter

    target = Path(args.target).expanduser().resolve()
    f = target / "agentlab" / "resilience" / "faults.py"
    if not f.is_file():
        return exit_missing(
            f"× 在 {target} 下没找到 agentlab/resilience/faults.py",
            "  用 --target 指到项目根目录（不是 src 里的子目录）",
            "  CONTRACT §1 要求故障注入器落在这个路径",
        )
    try:
        ctx = Ctx(target)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return exit_missing(f"× 导入失败：{type(exc).__name__}: {exc}", "  CONTRACT §1 要求 agentlab.tools.ToolResult 存在")

    return run_all(
        "P4-1 判分 · 故障注入框架",
        CHECKS,
        ctx,
        argv=rest,
        subtitle=f"目标 {target}",
        footer=(
            "注意：这里判的是「注入器本身对不对」。\n"
            "      卡里验收还要求「在 loop 里接入」——那部分要真跑一次 eval，离线判不了。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
