"""P1-3 判分：coroutine 到底并发了没有。

被判对象 `scripts/async_demo.py`。这张卡唯一的证据是**时间**：
同一个 `<0.8s×n>` 的任务，串行要 n×0.8s，并发只要 0.8s。
所以判分器真等——约 4 秒，不能造假替代。

除了时间，还有一条静态检查：async 函数里不许出现 `time.sleep`。
它不报错，只是卡住整个事件循环——所有协程一起等，输出看起来完全正常。

    python3 labs/p1-3/harness/run_checks.py --target ~/code/agentlab-project
"""
from __future__ import annotations

import ast
import asyncio
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "_shared"))
from checkkit import exit_missing, run_all  # noqa: E402

N = 3                       # 串行要 2.4s，并发 0.8s——差别足够明显
DELAY = 0.8
SERIAL_LO, SERIAL_HI = 2.0, 3.6
CONCURRENT_MAX = 1.6
SPEEDUP_MIN = 2.5
TIMEOUT_MSG = "超时被拦住"
FALLBACK = "不应该到这里"


class Ctx:
    def __init__(self, target: Path):
        self.target = target
        self.script = target / "scripts" / "async_demo.py"
        sys.path.insert(0, str(target))
        sys.path.insert(0, str(target / "scripts"))
        import async_demo as mod  # noqa: PLC0415

        self.mod = mod
        self.src = self.script.read_text(encoding="utf-8")
        self._cache: dict[str, object] = {}

    # ---- 计时 ----
    def run(self, coro):
        return asyncio.run(coro)

    def timed(self, fn, *args) -> float:
        t0 = time.perf_counter()
        self.run(fn(*args))
        return time.perf_counter() - t0

    def measured(self) -> dict:
        """四种耗时只量一次，后面复用——否则 self_test 会跑到天荒地老。"""
        if self._cache:
            return self._cache  # type: ignore[return-value]

        orig = self.mod.fake_llm
        self.seen: list[int] = []
        self.phase = ""

        async def recorder(client, idx):
            self.seen.append(idx)
            return await orig(client, idx)

        import httpx  # noqa: PLC0415  —— 夹具里的替身

        self.mod.fake_llm = recorder
        try:
            httpx.AsyncClient.made = 0
            self.phase = "serial"
            t_serial = self.timed(self.mod.serial, N)
            made_serial = httpx.AsyncClient.made

            seen_serial = list(self.seen)
            self.seen.clear()
            httpx.AsyncClient.made = 0
            self.phase = "concurrent"
            t_conc = self.timed(self.mod.concurrent, N)
            made_conc = httpx.AsyncClient.made
            seen_conc = list(self.seen)
        finally:
            self.mod.fake_llm = orig

        t_one = self.timed(self.mod.concurrent, 1)

        t0 = time.perf_counter()
        ret = self.run(self.mod.with_timeout())
        t_timeout = time.perf_counter() - t0

        self._cache = {
            "serial": t_serial, "conc": t_conc, "one": t_one,
            "made_serial": made_serial, "made_conc": made_conc,
            "seen_serial": seen_serial, "seen_conc": seen_conc,
            "timeout_ret": ret, "timeout": t_timeout,
        }
        return self._cache  # type: ignore[return-value]

    # ---- AST ----
    def async_sleeps(self) -> list[str]:
        tree = ast.parse(self.src)
        bad = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.AsyncFunctionDef,)):
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                    if sub.func.attr == "sleep":
                        owner = getattr(sub.func.value, "id", "")
                        if owner in ("time", "sleep"):
                            bad.append(f"{node.name}: {owner}.sleep")
        return bad

    def uses_gather(self) -> bool:
        for node in ast.walk(ast.parse(self.src)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ("gather", "wait", "create_task"):
                    return True
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "TaskGroup":
                return True
        return False


# ---------- 串行 ----------
def c1_serial_adds_up(ctx: Ctx) -> str:
    t = ctx.measured()["serial"]
    assert SERIAL_LO <= t <= SERIAL_HI, (
        f"serial({N}) 用了 {t:.2f}s，应在 {SERIAL_LO}–{SERIAL_HI}s"
        f"（{N} 次 × {DELAY}s = {N * DELAY:.1f}s）。\n"
        f"          太快说明没真等，太慢说明每次多了开销"
    )
    return f"{t:.2f}s ≈ {N}×{DELAY}s"


# ---------- 并发 ----------
def c2_concurrent_waits_once(ctx: Ctx) -> str:
    t = ctx.measured()["conc"]
    assert t < CONCURRENT_MAX, (
        f"concurrent({N}) 用了 {t:.2f}s（应 < {CONCURRENT_MAX}s）。\n"
        "          n 次调用只该等一次 0.8s。慢说明它们其实在排队——"
        "          最常见的原因是 async 函数里调了 time.sleep 或同步 IO"
    )
    return f"{t:.2f}s"


def c3_speedup(ctx: Ctx) -> str:
    m = ctx.measured()
    ratio = m["serial"] / m["conc"]
    assert ratio >= SPEEDUP_MIN, (
        f"加速比只有 {ratio:.1f}x（应 ≥ {SPEEDUP_MIN}x）——"
        f"串行 {m['serial']:.2f}s / 并发 {m['conc']:.2f}s。"
        "并发没生效，或者并发次数被写死了"
    )
    return f"{ratio:.1f}x"


def c4_scale_invariant(ctx: Ctx) -> str:
    """并发耗时与 n 无关，这才是「真并发」。

    只判 `concurrent(3) < 1.6` 不够：把 n 写死成 1 也能过。
    换两个 n 耗时基本不变，只有真并发做得到。
    """
    m = ctx.measured()
    one, three = m["one"], m["conc"]
    assert one > 0.4, (
        f"concurrent(1) 只用了 {one:.2f}s——比一次 0.8s 的延迟还短，说明根本没等够"
    )
    assert three < one * 1.4, (
        f"concurrent(1)={one:.2f}s 但 concurrent(3)={three:.2f}s（{three / one:.1f} 倍）。\n"
        "          并发 3 次不该比 1 次慢这么多——说明是「顺序 await」而不是 gather"
    )
    return f"1 次 {one:.2f}s / 3 次 {three:.2f}s"


def c5_order(ctx: Ctx) -> str:
    seen = ctx.measured()["seen_conc"]
    assert seen == list(range(N)), (
        f"并发时传入的 idx 是 {seen}，应为 {list(range(N))}。\n"
        "          gather 保序：结果的顺序和传入顺序一致，但执行是交错的一一"
        "          这正是它比 Promise.race 好用的地方"
    )
    return f"idx = {seen}"


# ---------- 超时 ----------
def c6_timeout_msg(ctx: Ctx) -> str:
    ret = ctx.measured()["timeout_ret"]
    assert ret == TIMEOUT_MSG, (
        f"with_timeout() 返回 {ret!r}，应为 {TIMEOUT_MSG!r}——"
        "超时没被拦住（TimeoutError 没接住）"
    )
    return ret


def c7_timeout_cut_short(ctx: Ctx) -> str:
    t = ctx.measured()["timeout"]
    assert t < 1.0, (
        f"with_timeout() 用了 {t:.2f}s——里面的 sleep(1) 已经跑完了，"
        "说明超时阈值没起作用。0.3s 的 timeout 应该打断它"
    )
    return f"{t:.2f}s 就返回了"


def c8_not_fallback(ctx: Ctx) -> str:
    ret = ctx.measured()["timeout_ret"]
    assert ret != FALLBACK, (
        f"返回了 {FALLBACK!r}——这说明 except 没接住 TimeoutError，"
        "或者超时块根本没抛（阈值设得比 1s 大）"
    )
    return "没走兜底分支"


# ---------- 静态 ----------
def c9_no_blocking_sleep(ctx: Ctx) -> str:
    bad = ctx.async_sleeps()
    assert not bad, (
        f"async 函数里有同步 sleep：{bad}。\n"
        "          它不报错，只是卡住整个事件循环——所有并发请求一起等，"
        "          输出看起来完全正常。这是这张卡最容易犯的错"
    )
    return "async 函数里没有 time.sleep"


def c10_uses_gather(ctx: Ctx) -> str:
    assert ctx.uses_gather(), (
        "并发路径里没有 gather / TaskGroup / create_task——"
        "那只可能是「顺序 await」，也就是串行"
    )
    return "用了 gather / TaskGroup"


def c11_client_once(ctx: Ctx) -> str:
    m = ctx.measured()
    assert m["made_serial"] == 1, (
        f"serial 里创建了 {m['made_serial']} 个 client（应为 1）——"
        "每个请求建一个连接池，等于放弃了连接复用"
    )
    assert m["made_conc"] == 1, (
        f"concurrent 里创建了 {m['made_conc']} 个 client（应为 1）——"
        "并发时更要注意：一个 client 是共享的连接池"
    )
    return "各自只建一个 client"


# ---------- 稳健 ----------
def c12_returns_idx(ctx: Ctx) -> str:
    async def check():
        import httpx  # noqa: PLC0415
        async with httpx.AsyncClient() as client:
            return await ctx.mod.fake_llm(client, 7)

    got = ctx.run(check())
    assert got == 7, f"fake_llm(client, 7) 返回了 {got!r}，应原样回传 7"
    return "idx 原样回传"


def c13_not_swallowing(ctx: Ctx) -> str:
    orig = ctx.mod.fake_llm

    async def boom(client, idx):
        raise RuntimeError("模拟某个请求失败")

    ctx.mod.fake_llm = boom
    try:
        ctx.run(ctx.mod.concurrent(2))
    except Exception as exc:  # noqa: BLE001
        if "模拟某个请求失败" in str(exc) or type(exc).__name__ == "ExceptionGroup":
            return f"异常被抛出（{type(exc).__name__}）"
        raise AssertionError(f"抛出了不相关的异常：{type(exc).__name__}: {exc}") from exc
    finally:
        ctx.mod.fake_llm = orig
    raise AssertionError(
        "有一个请求抛异常，但 concurrent() 正常返回了——异常被吞掉了。\n"
        "          gather 默认会把异常抛出来；如果你包了 try/except 又没重新抛，"
        "          调用方会以为「全部成功」，而实际有一路失败了"
    )


CHECKS = [
    ("串行把等待叠加起来", c1_serial_adds_up),
    ("并发只等一次", c2_concurrent_waits_once),
    ("加速比 ≥2.5 倍", c3_speedup),
    ("并发耗时与 n 无关", c4_scale_invariant),
    ("并发保序", c5_order),
    ("超时被拦住", c6_timeout_msg),
    ("超时真的截断了", c7_timeout_cut_short),
    ("没走兜底分支", c8_not_fallback),
    ("async 里没有 time.sleep", c9_no_blocking_sleep),
    ("用了 gather / TaskGroup", c10_uses_gather),
    ("client 只建一个", c11_client_once),
    ("fake_llm 原样回传 idx", c12_returns_idx),
    ("异常不被吞掉", c13_not_swallowing),
]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="判 P1-3 的并发实验")
    ap.add_argument("--target", default=".", help="项目根目录（含 scripts/）")
    args, rest = ap.parse_known_args()

    target = Path(args.target).expanduser().resolve()
    if not (target / "scripts" / "async_demo.py").is_file():
        return exit_missing(
            f"× 在 {target} 下没找到 scripts/async_demo.py",
            "  用 --target 指到项目根目录",
            "  CONTRACT §1 要求 serial / concurrent / with_timeout 在这里",
        )
    try:
        ctx = Ctx(target)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return exit_missing(f"× 导入失败：{type(exc).__name__}: {exc}")

    return run_all(
        "P1-3 判分 · coroutine 与并发",
        CHECKS,
        ctx,
        argv=rest,
        subtitle=f"目标 {target}（要真等约 4 秒）",
        footer=(
            "注意：这里判「时间差」。\n"
            "      时间是这张卡唯一的证据——并发没生效时，只有耗时会露出来。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
