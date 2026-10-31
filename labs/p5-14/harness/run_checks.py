"""P5-14 判分：特性开关与消融。

被判对象两处：
    `agentlab/flags.py`     Flags 定义 + load() 的优先级
    `scripts/ablate.py`     一次关一个特性，打印差值

消融那部分把 `run_eval` 换成一个**记录参数的假 eval**：
不联网、不花钱，但能看清「每次传进去的 flags 是什么」。
「一次只关一个」和「基线只算一次」这两条只有这样才判得出来。

    python3 labs/p5-14/harness/run_checks.py --target ~/code/agentlab-project
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "_shared"))
from checkkit import exit_missing, run_all  # noqa: E402

DEFAULTS = {
    "query_rewrite": True,
    "rerank": True,
    "self_check": False,
    "cache_prefix": True,
}
PREFIX = "AIP_"

# 假 eval：只认 flags 参数，记录每次调用，返回带三个指标的对象
EVALS_STUB = '''"""判分夹具：假 eval，把每次调用的 flags 记到 _calls.jsonl。"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path


class Metrics:
    def __init__(self, pass5: float, cost: float, p95: float) -> None:
        self.pass5 = pass5
        self.cost = cost
        self.p95 = p95

    def __repr__(self) -> str:
        return f"Metrics(pass5={self.pass5}, cost={self.cost}, p95={self.p95})"


def run_eval(*, flags=None, **kwargs) -> Metrics:
    rec = asdict(flags) if flags is not None else {}
    with Path("_calls.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\\n")
    # 数值随「关掉几个」变化，模拟「特性有效」的样子
    off = sum(1 for v in rec.values() if not v) if isinstance(rec, dict) else 0
    return Metrics(pass5=0.80 - 0.03 * off, cost=0.050 - 0.004 * off, p95=1200 - 40 * off)
'''


class Ctx:
    def __init__(self, target: Path):
        self.target = target
        self.flags_path = target / "agentlab" / "flags.py"
        self.ablate_path = target / "scripts" / "ablate.py"
        sys.path.insert(0, str(target))
        from agentlab import flags as mod  # noqa: PLC0415

        self.mod = mod
        self.Flags = mod.Flags
        self.load = mod.load
        self.fields = list(mod.Flags.__dataclass_fields__)

        # ---- 消融部分：在沙箱里跑 ----
        self._sbx = tempfile.TemporaryDirectory(prefix="p5-14-sbx-")
        root = Path(self._sbx.name)
        (root / "agentlab").mkdir()
        (root / "scripts").mkdir()
        (root / "agentlab" / "__init__.py").write_text("", encoding="utf-8")
        shutil.copy2(self.flags_path, root / "agentlab" / "flags.py")
        (root / "agentlab" / "evals.py").write_text(EVALS_STUB, encoding="utf-8")
        self.has_ablate = self.ablate_path.is_file()
        if self.has_ablate:
            shutil.copy2(self.ablate_path, root / "scripts" / "ablate.py")
        self.root = root
        self.calls: list[dict] = []
        self.ablate_rc = None
        self.ablate_out = ""
        if self.has_ablate:
            env = dict(os.environ)
            env["PYTHONPATH"] = str(root)
            r = subprocess.run(
                [sys.executable, str(root / "scripts" / "ablate.py")], cwd=str(root),
                capture_output=True, text=True, timeout=180, env=env,
            )
            self.ablate_rc = r.returncode
            self.ablate_out = r.stdout + r.stderr
            log = root / "_calls.jsonl"
            if log.exists():
                for line in log.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        self.calls.append(json.loads(line))

    # ---- 辅助 ----
    def with_env(self, mapping: dict[str, str]):
        """临时设环境变量，返回清理函数（务必 try/finally 调它）。"""
        old = {k: os.environ.get(k) for k in mapping}
        os.environ.update(mapping)

        def restore() -> None:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

        return restore

    def clear_env(self) -> None:
        for f in DEFAULTS:
            os.environ.pop(f"{PREFIX}{f.upper()}", None)

    def baseline_calls(self) -> list[dict]:
        return [c for c in self.calls if c == DEFAULTS]

    @staticmethod
    def changed(call: dict) -> list[str]:
        """这次调用相对默认值改了哪些字段（不管改开还是改关）。"""
        return [f for f, v in call.items() if f in DEFAULTS and v != DEFAULTS[f]]


# ---------- 开关定义 ----------
def c1_defaults(ctx: Ctx) -> str:
    lack = [f for f in DEFAULTS if f not in ctx.fields]
    assert not lack, f"Flags 缺字段 {lack}——消融的目标就是这几个"
    got = {f: getattr(ctx.Flags(), f) for f in DEFAULTS}
    diff = {f: (got[f], DEFAULTS[f]) for f in DEFAULTS if got[f] != DEFAULTS[f]}
    assert not diff, f"默认值与 CONTRACT 不一致（实际, 期望）：{diff}"
    return "、".join(f"{f}={got[f]}" for f in DEFAULTS)


def c2_frozen(ctx: Ctx) -> str:
    f = ctx.Flags()
    try:
        f.rerank = False
    except Exception as exc:  # noqa: BLE001
        return f"不可变（{type(exc).__name__}）"
    raise AssertionError(
        "Flags 可以被原地修改——开关对象一旦可变，某个中间层改了它，"
        "整条链路上后面的调用都会受影响，而你以为只是「试一下」"
    )


# ---------- 优先级 ----------
def c3_load_default(ctx: Ctx) -> str:
    ctx.clear_env()
    got = ctx.load()
    diff = {f: (getattr(got, f), DEFAULTS[f]) for f in DEFAULTS if getattr(got, f) != DEFAULTS[f]}
    assert not diff, f"load() 无参时没返回默认值：{diff}"
    return "remote 与 env 都空 → 默认"


def c4_remote_wins(ctx: Ctx) -> str:
    ctx.clear_env()
    restore = ctx.with_env({f"{PREFIX}RERANK": "1"})
    try:
        got = ctx.load({"rerank": False})
    finally:
        restore()
    assert got.rerank is False, (
        f"remote 说 rerank=False，环境变量说 =1，load() 取了 {got.rerank}——"
        "应该 remote 优先。远程那层是「线上出问题不想等发版」用的，被环境变量盖掉就失去意义"
    )
    return "remote 盖过环境变量"


def c5_env_wins(ctx: Ctx) -> str:
    ctx.clear_env()
    restore = ctx.with_env({f"{PREFIX}CACHE_PREFIX": "0"})
    try:
        got = ctx.load()
    finally:
        restore()
    assert got.cache_prefix is False, (
        f"AIP_CACHE_PREFIX=0 但 cache_prefix={got.cache_prefix}——环境变量没生效"
    )
    return "环境变量盖过默认"


def c6_env_only_one(ctx: Ctx) -> str:
    ctx.clear_env()
    for raw, want in [("0", False), ("true", False), ("1", True)]:
        restore = ctx.with_env({f"{PREFIX}RERANK": raw})
        try:
            got = ctx.load()
        finally:
            restore()
        assert got.rerank is want, (
            f"AIP_RERANK={raw!r} 时 rerank={got.rerank}，期望 {want}。\n"
            "          只有字符串 '1' 算开。'0' 和 'false' 都是非空字符串，"
            "          `if os.getenv(...)` 会把它们判成真——这是运维最常踩的一脚"
        )
    return "'1' 开，'0'/'true' 关"


def c7_each_field_has_entry(ctx: Ctx) -> str:
    ctx.clear_env()
    bad = []
    for f in DEFAULTS:
        restore = ctx.with_env({f"{PREFIX}{f.upper()}": "0"})
        try:
            got = getattr(ctx.load(), f)
        finally:
            restore()
        if got is not False:
            bad.append(f)
    assert not bad, (
        f"这些字段没有独立的环境变量入口：{bad}——"
        "线上要能单独关掉一个特性，缺一个就等于那个特性关不掉"
    )
    return f"{len(DEFAULTS)} 个字段都能单独关"


def c8_unknown_remote_key(ctx: Ctx) -> str:
    ctx.clear_env()
    try:
        got = ctx.load({"no_such_flag": True, "rerank": False})
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(
            f"remote 里多了一个未知 key，load() 抛了 {type(exc).__name__}: {exc}。\n"
            "          远程配置里多一个字段（灰度、实验分组）就会让整个 load 崩——"
            "而这一层本来就是「紧急改了要立即生效」用的，最不能崩"
        ) from exc
    assert got.rerank is False, "未知 key 存在时，已知的那个字段也没生效"
    return "未知 key 被忽略，其余照常"


# ---------- 返回 ----------
def c9_returns_flags(ctx: Ctx) -> str:
    ctx.clear_env()
    got = ctx.load()
    assert isinstance(got, ctx.Flags), f"load() 返回了 {type(got).__name__}，应为 Flags"
    return "返回 Flags 实例"


# ---------- 消融 ----------
def _need_ablate(ctx: Ctx) -> None:
    assert ctx.has_ablate, "找不到 scripts/ablate.py"
    assert ctx.ablate_rc == 0, (
        f"ablate.py 退出码 {ctx.ablate_rc}。输出末几行：\n"
        + "\n".join(ctx.ablate_out.strip().splitlines()[-6:])
    )


def c10_ablate_runs(ctx: Ctx) -> str:
    _need_ablate(ctx)
    return "退出码 0"


def c11_one_at_a_time(ctx: Ctx) -> str:
    """每次调用与默认值相比，至多差一个字段。

    注意这里判的是「差几个」，不是「关了几个」：self_check 默认为 False，
    「关掉它」不算改动，见下一条。
    """
    _need_ablate(ctx)
    for c in ctx.calls:
        diff = ctx.changed(c)
        assert len(diff) <= 1, (
            f"有一次调用同时改了 {len(diff)} 个特性 {diff}——"
            "一次改多个，你无法把效果归到某一个特性上，那就不是消融"
        )
    return "每次最多动一个"


def c12_each_actually_changed(ctx: Ctx) -> str:
    """每个特性都必须**真的被改过**至少一次。

    `self_check` 的默认值是 False，所以 `replace(BASE, self_check=False)` 什么也没改——
    这次对比两边一模一样，delta 恒为 0，而你会把它读成「自检没有效果」。
    要测一个默认关着的特性，得把它打开，而不是「关掉」。
    """
    _need_ablate(ctx)
    touched = {f for c in ctx.calls for f in ctx.changed(c)}
    vacuous = [f for f in DEFAULTS if f not in touched]
    assert not vacuous, (
        f"这些特性的「消融」其实什么都没改：{vacuous}。\n"
        "          默认就关着的特性，`replace(BASE, x=False)` 等于没动，"
        "这次对比两边一样，delta 恒为 0——你会把它读成「这个特性没用」"
    )
    return "每个特性都真的被改动过"


def c13_baseline_once(ctx: Ctx) -> str:
    """基线只算一次。参考实现把它写在循环里。"""
    _need_ablate(ctx)
    n = len(ctx.baseline_calls())
    assert n == 1, (
        f"全开的基线跑了 {n} 次。基线必须在循环外算一次——\n"
        "          每次对比用不同基线，delta 里就混进了采样噪声，\n"
        "          四个特性之间的差值互相不可比，而这恰恰是消融唯一要回答的问题"
    )
    return "基线只算一次"


def c14_reports_metrics(ctx: Ctx) -> str:
    _need_ablate(ctx)
    out = ctx.ablate_out
    for need, why in [("Pass", "通过率（目标指标）"), ("成本", "成本（护栏之一）")]:
        assert need in out, (
            f"ablate.py 的输出里没有「{need}」——消融要同时报{why}，"
            "只报一个的话，「更准了但贵了一倍」这种结论看不出来"
        )
    return "报了 Pass@5 与成本"


def c15_one_line_each(ctx: Ctx) -> str:
    _need_ablate(ctx)
    lines = [ln for ln in ctx.ablate_out.splitlines() if any(f in ln for f in DEFAULTS)]
    assert len(set(lines)) >= len(DEFAULTS), (
        f"输出里只找到 {len(set(lines))} 行特性结果，应有 {len(DEFAULTS)} 行"
        "（一行一个特性，否则结论散在段落里没法比）"
    )
    return f"{len(set(lines))} 行结果"


CHECKS = [
    ("Flags 四个字段与默认值", c1_defaults),
    ("Flags 不可变", c2_frozen),
    ("load() 无参返回默认", c3_load_default),
    ("remote 优先于环境变量", c4_remote_wins),
    ("环境变量优先于默认", c5_env_wins),
    ("环境变量只认 '1'", c6_env_only_one),
    ("每个字段都有独立入口", c7_each_field_has_entry),
    ("未知 remote key 不崩", c8_unknown_remote_key),
    ("load() 返回 Flags", c9_returns_flags),
    ("消融脚本能跑", c10_ablate_runs),
    ("每次只关一个", c11_one_at_a_time),
    ("每个特性都真的被改过", c12_each_actually_changed),
    ("基线只算一次", c13_baseline_once),
    ("报了 Pass@5 与成本", c14_reports_metrics),
    ("一行一个特性", c15_one_line_each),
]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="判 P5-14 的开关与消融")
    ap.add_argument("--target", default=".", help="项目根目录（含 agentlab/ 与 scripts/）")
    args, rest = ap.parse_known_args()

    target = Path(args.target).expanduser().resolve()
    if not (target / "agentlab" / "flags.py").is_file():
        return exit_missing(
            f"× 在 {target} 下没找到 agentlab/flags.py",
            "  用 --target 指到项目根目录",
            "  CONTRACT §1 要求 Flags 与 load() 在这里",
        )
    try:
        ctx = Ctx(target)
    except subprocess.TimeoutExpired:
        return exit_missing("× ablate.py 跑了 180 秒还没结束——检查是不是死循环了")
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return exit_missing(f"× 导入失败：{type(exc).__name__}: {exc}")

    return run_all(
        "P5-14 判分 · 开关与消融",
        CHECKS,
        ctx,
        argv=rest,
        subtitle=f"目标 {target}",
        footer=(
            "注意：这里判「消融的组织方式」，判不了「哪个特性真有用」。\n"
            "      真消融要真实流量 + 成本看板 + 跑得动的 eval，三个前提一个都不能少。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
