"""P3-5 判分：system prompt 的分层与前缀稳定性。

被判对象 `agentlab/prompt.py`：`build_system(extra="") -> str`。

这张卡的核心不是「写好 prompt」，是**排布**：越靠前越稳定。
缓存按前缀匹配，前缀一变缓存全废——而排错了的代码看起来完全正常，
只有账单和 p95 会告诉你。

判分器把模块里的 `datetime` 换成假钟，就是为了让「时间变了」这件事真的发生，
否则两次调用一字不差，前缀稳不稳定根本测不出来。

    python3 labs/p3-5/harness/run_checks.py --target ~/code/agentlab-project
"""
from __future__ import annotations

import re
import sys
import traceback
from datetime import datetime as _real_dt
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "_shared"))
from checkkit import exit_missing, run_all  # noqa: E402

# 五段的锚点。取「段落小标题」而不是整段话——措辞可以改，主题不能少
ANCHORS = {
    "身份": ("助手",),
    "能力边界": ("能力边界",),
    "工具使用规则": ("工具使用规则",),
    "输出要求": ("输出要求",),
    "当前环境": ("当前环境",),
}
ORDER = ["身份", "能力边界", "工具使用规则", "输出要求", "当前环境"]


class Clock:
    """假钟：替换 prompt 模块里的 `datetime`，让两次调用落在不同分钟。"""

    def __init__(self, stamp: str):
        self.stamp = stamp

    def now(self) -> _real_dt:
        return _real_dt.strptime(self.stamp, "%Y-%m-%d %H:%M")


class Ctx:
    def __init__(self, target: Path):
        self.target = target
        sys.path.insert(0, str(target))
        from agentlab import prompt as mod  # noqa: PLC0415

        self.mod = mod
        self.build_system = mod.build_system
        self.real_dt = getattr(mod, "datetime", _real_dt)

    def at(self, stamp: str, extra: str = "") -> str:
        self.mod.datetime = Clock(stamp)
        try:
            out = self.build_system(extra)
        finally:
            self.mod.datetime = self.real_dt
        assert isinstance(out, str), f"build_system 返回了 {type(out).__name__}，应为 str"
        return out

    def plain(self, extra: str = "") -> str:
        out = self.build_system(extra)
        assert isinstance(out, str), f"build_system 返回了 {type(out).__name__}，应为 str"
        return out


def _prefix_len(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def _need_prefix(text: str) -> tuple[int, str]:
    """公共前缀至少要覆盖到「输出要求」段结束（= 最后一个静态段）。"""
    i = text.find("输出要求")
    assert i >= 0, "找不到「输出要求」段"
    j = text.find("\n\n", i)
    return (j if j >= 0 else len(text)), text[i:i + 40].replace("\n", "⏎")


# ---------- 五段都在，顺序对 ----------
def c1_not_empty(ctx: Ctx) -> str:
    out = ctx.at("2026-03-01 09:00")
    assert out.strip(), "build_system() 返回空串"
    return f"{len(out)} 字符"


def c2_five_parts(ctx: Ctx) -> str:
    out = ctx.at("2026-03-01 09:00")
    lack = [name for name, keys in ANCHORS.items() if not any(k in out for k in keys)]
    assert not lack, (
        f"缺段落 {lack}。五段各管一件事：身份（你是谁）、边界（不能做什么）、"
        "工具规则（什么时候调）、输出要求（怎么答）、当前环境（每轮变的）"
    )
    return "五段齐全"


def c3_order(ctx: Ctx) -> str:
    out = ctx.at("2026-03-01 09:00")
    pos = []
    for name in ORDER:
        cand = [out.find(k) for k in ANCHORS[name] if out.find(k) >= 0]
        assert cand, f"找不到「{name}」段"
        pos.append((min(cand), name))
    assert pos == sorted(pos), (
        "五段顺序不对，实际是 " + " → ".join(n for _, n in pos) +
        f"；应为 {' → '.join(ORDER)}（越靠前越稳定）"
    )
    return " → ".join(n for _, n in pos)


# ---------- 前缀稳定：这张卡的核心 ----------
def c4_prefix_stable_across_time(ctx: Ctx) -> str:
    a = ctx.at("2026-03-01 09:00")
    b = ctx.at("2026-03-01 15:47")
    assert a != b, (
        "换了两分钟之后输出完全相同——说明动态段没读时间，"
        "或者你换了别的取时间方式（假钟打不进去）。见 CONTRACT §3"
    )
    k = _prefix_len(a, b)
    need, seg = _need_prefix(a)
    assert k >= need, (
        f"公共前缀只有 {k} 字符，但覆盖前四段需要 {need} 字符（差 {need - k}）。\n"
        "          「当前环境」这类每轮都变的内容排到了静态段前面——"
        "缓存按前缀匹配，前缀一变全废，延迟和成本一起回来，而代码看起来完全正常"
    )
    return f"前缀 {k} 字符 ≥ {need}"


def c5_prefix_stable_across_extra(ctx: Ctx) -> str:
    base = ctx.at("2026-03-01 09:00")
    a = ctx.at("2026-03-01 09:00", extra="这次只回答一个词")
    b = ctx.at("2026-03-01 09:00", extra="这次要给出三条建议")
    assert a != b, "extra 变了但输出没变——extra 没被拼进去"
    k = _prefix_len(a, b)
    assert k >= len(base), (
        f"extra 变了之后公共前缀只剩 {k} 字符，但两版共有的部分有 {len(base)} 字符——"
        "说明 extra 插到了静态段中间，等于每次换任务都把缓存清一遍"
    )
    return f"前缀 {k} 字符 ≥ {len(base)}"


def c6_extra_last(ctx: Ctx) -> str:
    out = ctx.at("2026-03-01 09:00", extra="这是一段很特别的补充说明")
    i_extra = out.find("这是一段很特别的补充说明")
    i_env = out.find("当前环境")
    assert i_extra >= 0, "extra 没出现在输出里"
    assert i_env >= 0, "找不到「当前环境」段"
    assert i_extra > i_env, (
        "extra 排在「当前环境」之前。extra 是最不稳定的东西（每个任务都不一样），"
        "必须放最后；放中间等于把后面所有内容都推出缓存"
    )
    return "extra 在末尾"


# ---------- 拼接 ----------
def c7_separator(ctx: Ctx) -> str:
    out = ctx.at("2026-03-01 09:00")
    assert "\n\n" in out, "段之间没有空行——拼成一大坨，读起来和改起来都容易串段"
    assert "\n\n\n" not in out, (
        "出现连续三个换行：某一段首尾自带空行，和 `\\n\\n` 拼出了两层空隙。"
        "用 `p.strip()` 再拼就能避免"
    )
    return "空行分隔，无三连换行"


# ---------- 内容 ----------
def c8_file_count(ctx: Ctx) -> str:
    n = len(list((ctx.target / "data" / "corpus").glob("*.md")))
    assert n > 0, f"夹具里 data/corpus 没有 .md 文件（{n} 个），这条测不出来"
    out = ctx.at("2026-03-01 09:00")
    # 取「文件…数字」里**最后**一处：环境段在末尾，前面的边界段也可能提到文件
    hits = re.findall(r"文件[^\n]{0,12}?(\d+)", out)
    assert hits, (
        "输出里找不到「文件…数字」这样的计数（形如「语料文件数：3」）——"
        "不报数字，模型就没法判断语料规模"
    )
    got = int(hits[-1])
    assert got == n, (
        f"输出里的文件数是 {got}，但 data/corpus 下实际有 {n} 个 .md——"
        "写死的数字会让模型对语料规模的判断永远过期。"
        "顺便一提：不要用 `str(n) in out` 判这件事，日期里的数字会把这条断言蒙过去"
    )
    return f"文件数 {got} 与目录一致（{n}）"


def c9_boundaries(ctx: Ctx) -> str:
    out = ctx.at("2026-03-01 09:00")
    for path in ("data/", "notes/"):
        assert path in out, f"能力边界里没写 {path}——不写死目录，模型会去读 /etc/passwd 那类东西"
    return "目录边界写死了"


def c10_tool_limit(ctx: Ctx) -> str:
    out = ctx.at("2026-03-01 09:00")
    # 要「数字 + 次」，不是只要有「次」——「一次可以调多个」里也有「次」
    m = re.search(r"(\d+)\s*次", out)
    assert m, (
        "工具规则里没有数字形式的次数上限（形如「最多 6 次工具调用」）。"
        "没有上限的 agent 会在一个查不到的问题上反复调用，直到把预算烧完"
    )
    return f"上限 {m.group(1)} 次"


def c11_uncertainty(ctx: Ctx) -> str:
    out = ctx.at("2026-03-01 09:00")
    assert "不确定" in out, (
        "输出要求里没有「不确定」的写法——不说清怎么表达不确定，模型倾向编一个确定的答案"
    )
    return "有不确定标注规则"


# ---------- 干净 ----------
def c12_no_empty_extra_title(ctx: Ctx) -> str:
    out = ctx.at("2026-03-01 09:00", extra="")
    assert "本次任务补充说明" not in out, (
        "extra 为空时仍拼上了「本次任务补充说明」这个标题——空标题会让模型等一段"
        "不存在的说明，也白白污染前缀"
    )
    return "空 extra 不留标题"


def c13_pure(ctx: Ctx) -> str:
    a = ctx.at("2026-03-01 09:00")
    b = ctx.at("2026-03-01 09:00")
    assert a == b, "同一时刻两次调用结果不同——除时间和文件数之外还读了别的东西"
    return "同一时刻结果一致"


def c14_dynamic_is_dynamic(ctx: Ctx) -> str:
    out = ctx.at("2026-03-01 09:00")
    tail = out[out.find("当前环境"):] if "当前环境" in out else out[-400:]
    for static in ("能力边界", "工具使用规则", "输出要求"):
        assert static not in tail, (
            f"「{static}」出现在「当前环境」之后——静态规则混进了动态段，"
            "等于每轮都重发一遍规则，还让前缀变长"
        )
    return "动态段只放动态信息"


CHECKS = [
    ("返回非空", c1_not_empty),
    ("五段齐全", c2_five_parts),
    ("五段顺序对", c3_order),
    ("时间变了前缀仍稳定", c4_prefix_stable_across_time),
    ("extra 变了前缀仍稳定", c5_prefix_stable_across_extra),
    ("extra 在末尾", c6_extra_last),
    ("空行分隔且无三连换行", c7_separator),
    ("文件数来自目录", c8_file_count),
    ("能力边界写了目录", c9_boundaries),
    ("工具规则有次数上限", c10_tool_limit),
    ("输出要求含不确定", c11_uncertainty),
    ("空 extra 不留标题", c12_no_empty_extra_title),
    ("同一时刻结果一致", c13_pure),
    ("动态段只放动态信息", c14_dynamic_is_dynamic),
]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="判 P3-5 的 prompt 分层")
    ap.add_argument("--target", default=".", help="项目根目录（含 agentlab/）")
    args, rest = ap.parse_known_args()

    target = Path(args.target).expanduser().resolve()
    if not (target / "agentlab" / "prompt.py").is_file():
        return exit_missing(
            f"× 在 {target} 下没找到 agentlab/prompt.py",
            "  用 --target 指到项目根目录",
            "  CONTRACT §1 要求 build_system() 在这里",
        )
    try:
        ctx = Ctx(target)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return exit_missing(f"× 导入失败：{type(exc).__name__}: {exc}")

    return run_all(
        "P3-5 判分 · prompt 分层组装",
        CHECKS,
        ctx,
        argv=rest,
        subtitle=f"目标 {target}",
        footer=(
            "注意：这里判「排布」——五段齐、顺序对、前缀稳。\n"
            "      措辞好不好、缓存命中率多少，要真跑两次请求看 cached_tokens，离线判不了。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
