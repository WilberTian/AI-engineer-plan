"""P1-8 判分：错误探测脚本打出来的东西够不够定位用。

被判对象 `scripts/error_probe.py`。`openai` 与 `agentlab.config.PRIMARY`
由判分器提供替身，替身会按参数抛不同形状的异常：
有的带 status_code、有的不带、有的消息超长。

判的是「输出格式」不是「错误码表」——后者只能真调供应商一次，
结果不可复现，而且供应商改文案就漂。

    python3 labs/p1-8/harness/run_checks.py --target ~/code/agentlab-project
"""
from __future__ import annotations

import contextlib
import io
import re
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "_shared"))
from checkkit import exit_missing, run_all  # noqa: E402

MAX_MSG = 200


class Ctx:
    def __init__(self, target: Path):
        self.target = target
        self.script = target / "scripts" / "error_probe.py"
        sys.path.insert(0, str(target))
        sys.path.insert(0, str(target / "scripts"))

        import openai as stub  # noqa: PLC0415  —— 夹具里的替身，不是真 SDK

        self.stub = stub
        self.stub.CALLS.clear()
        self.stub.RAISE = True
        buf = io.StringIO()
        # stderr 一起收：traceback 默认打到 stderr，只看 stdout 会漏掉它
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            import error_probe as mod  # noqa: PLC0415
        self.mod = mod
        self.out = buf.getvalue()
        self.calls = list(self.stub.CALLS)

    # ---- 解析输出 ----
    def labels(self) -> list[str]:
        return re.findall(r"^\s*\[(.+?)\]\s*$", self.out, re.M)

    def field_values(self, name: str) -> list[str]:
        return re.findall(rf"^\s*{name}\s*=\s*(.*)$", self.out, re.M)


# ---------- 不崩 ----------
def c1_survives(ctx: Ctx) -> str:
    assert ctx.calls, (
        "一次都没有调用到 create——probe() 没把参数传下去，"
        "或者脚本在 import 时就失败了"
    )
    return f"{len(ctx.calls)} 次探测都跑完了"


# ---------- 三样 ----------
def c2_labels(ctx: Ctx) -> str:
    labels = ctx.labels()
    assert len(labels) >= 5, (
        f"输出里只找到 {len(labels)} 个 [label]，应有 5 个（每类错误一个）。\n"
        f"          实际输出片段：{ctx.out.strip()[:200]!r}"
    )
    return f"{len(labels)} 个 label"


def c3_three_lines(ctx: Ctx) -> str:
    for name, why in [("type", "异常类型决定走哪条处理分支"),
                      ("status", "HTTP 状态码决定「重试还是改参数」"),
                      ("message", "消息前 200 字覆盖剩下 90% 的定位")]:
        vals = ctx.field_values(name)
        assert len(vals) >= 5, (
            f"输出里 {name}= 只出现 {len(vals)} 次，应有 5 次（每次探测一条）。\n"
            f"          {name} 管什么：{why}"
        )
    return "type / status / message 各 5 条"


# ---------- 兜底 ----------
def c4_missing_status(ctx: Ctx) -> str:
    """`max_tokens=-1` 那条抛的是没有 status_code 的异常。"""
    vals = ctx.field_values("status")
    assert "None" in vals, (
        f"没有任何一条 status 打印成 None（实际 {vals}）。\n"
        "          有一类错误（参数校验失败）根本没有 status_code，"
        "          用 `exc.status_code` 直接取会崩；要 getattr 兜底"
    )
    return "缺 status_code 时打印 None"


# ---------- 截断 ----------
def c5_truncated(ctx: Ctx) -> str:
    vals = ctx.field_values("message")
    longest = max((len(v) for v in vals), default=0)
    assert longest <= MAX_MSG + 10, (
        f"最长的一条 message 有 {longest} 字（应 ≤{MAX_MSG}）。\n"
        "          超长错误体（比如整页 HTML 的 502）不截断会淹掉另外两样，"
        "          而它们才是你真正的定位入口"
    )
    # 夹具里有一条 500 字的错误消息。没有一条接近 200 字，说明根本没走到 SDK——
    # 否则「不截断」这个错法永远不会被观察到（这正是「断言因为没执行而通过」）
    assert longest >= 190, (
        f"最长的一条 message 才 {longest} 字，而夹具里有一条 500 字的错误体。\n"
        "          说明五次探测没真正调到 SDK（见 CONTRACT §2），"
        "          所以「截断」这条判据实际上一行都没被执行过"
    )
    return f"最长 {longest} 字（已截断）"


# ---------- 可区分 ----------
def c6_labels_unique(ctx: Ctx) -> str:
    labels = ctx.labels()
    dup = {x for x in labels if labels.count(x) > 1}
    assert not dup, f"label 重复：{sorted(dup)[:3]}——分不清是哪次探测"
    return "五个 label 互不重复"


def c7_no_traceback(ctx: Ctx) -> str:
    assert "Traceback (most recent call last)" not in ctx.out, (
        "输出里有完整 traceback——探测脚本的目的是看清错误结构，"
        "不是记录事故。30 行 traceback 会把 type/status/message 三行淹掉"
    )
    return "没有 traceback"


# ---------- 透传 ----------
def c8_kwargs_passed(ctx: Ctx) -> str:
    n = len(ctx.calls)
    assert n == 5, f"create 被调了 {n} 次，应有 5 次（五次探测各一次）"
    shapes = {tuple(sorted((k, str(v)[:20]) for k, v in c.items())) for c in ctx.calls}
    assert len(shapes) == n, (
        f"五次调用里有重复的参数组合（{len(shapes)} 种 / {n} 次）——\n"
        "          说明 probe() 把 kwargs 吞掉了，五次探测都变成了同一种错误。"
        "          输出照样有五行，内容全一样，而你以为「五种都看过了」"
    )
    return "五次参数各不相同"


def c9_messages_present(ctx: Ctx) -> str:
    assert ctx.calls, "一次都没调 create，这条无从判起（先修透传，见 CONTRACT §2）"
    lack = [i for i, c in enumerate(ctx.calls, 1) if "messages" not in c]
    assert not lack, (
        f"第 {lack} 次调用没有 messages 参数——"
        "`probe()` 里写死 messages=[] 就会这样：每次探测都真的发了空消息，"
        "于是你「踩的五种坑」其实是同一个坑踩五次"
    )
    return "五次都带了 messages"


def c10_model_override(ctx: Ctx) -> str:
    models = {c.get("model") for c in ctx.calls if c.get("model")}
    base = getattr(ctx.stub, "PRIMARY_MODEL", None)
    other = {m for m in models if m != base}
    assert other, (
        "五次探测都用了同一个模型名——「错误模型名」这一类坑没踩到。\n"
        "          模型不存在时的错误形状（404 vs 400）和其他类完全不同，"
        "          定位时最容易误判成「参数写错」"
    )
    return f"改过模型名：{sorted(other)}"


# ---------- 静默 ----------
def c11_silent_on_success(ctx: Ctx) -> str:
    ctx.stub.RAISE = False
    ctx.stub.CALLS.clear()
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            ctx.mod.probe("这条不会报错", messages=[{"role": "user", "content": "hi"}])
    finally:
        ctx.stub.RAISE = True
    assert buf.getvalue().strip() == "", (
        f"调用成功时也打印了内容：{buf.getvalue().strip()[:120]!r}\n"
        "          探测脚本只在出错时输出，成功时保持安静——"
        "否则真实运行时 90% 的行都是噪音"
    )
    return "成功时保持安静"


CHECKS = [
    ("五次探测都跑完了", c1_survives),
    ("五个 label 都在", c2_labels),
    ("三样各打五条", c3_three_lines),
    ("缺 status_code 时打印 None", c4_missing_status),
    ("超长消息被截断", c5_truncated),
    ("label 互不重复", c6_labels_unique),
    ("没有 traceback", c7_no_traceback),
    ("kwargs 真的透传了", c8_kwargs_passed),
    ("每次都在探新参数", c9_messages_present),
    ("踩过「模型名错」这一类", c10_model_override),
    ("成功时不打印", c11_silent_on_success),
]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="判 P1-8 的错误探测脚本")
    ap.add_argument("--target", default=".", help="项目根目录（含 scripts/）")
    args, rest = ap.parse_known_args()

    target = Path(args.target).expanduser().resolve()
    if not (target / "scripts" / "error_probe.py").is_file():
        return exit_missing(
            f"× 在 {target} 下没找到 scripts/error_probe.py",
            "  用 --target 指到项目根目录",
            "  CONTRACT §1 要求这个脚本在这里",
        )
    try:
        ctx = Ctx(target)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return exit_missing(f"× 跑脚本失败：{type(exc).__name__}: {exc}")

    return run_all(
        "P1-8 判分 · 错误探测",
        CHECKS,
        ctx,
        argv=rest,
        subtitle=f"目标 {target}（openai 是替身）",
        footer=(
            "注意：这里判「打出来的东西够不够定位」。\n"
            "      真正的错误码表必须你自己调一次供应商——那是这张卡不可替代的部分。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
