"""P2-10 判分：拒答的两层判据。

被判对象 `agentlab/rag/answer.py`：`answer(question, top_score, chunks) -> (text, reason)`。

判的是**两层都在，而且顺序对**：
第一层是硬门槛（不调模型就拒），第二层是模型出口（给了出口才谈得上「老实说不知道」）。
只做第二层，模型会尽力回答；只做第一层，过度拒答没人管。

    python3 labs/p2-10/harness/run_checks.py --target ~/code/agentlab-project
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "_shared"))
from checkkit import exit_missing, run_all  # noqa: E402

THRESHOLD = 0.35
REASONS = {"refused_low_score", "refused_by_model", "answered"}
CHUNK = {"doc_id": "d1.md", "section": "1", "text": "默认端口是 8080。"}
REPLY = "默认端口是 8080（来源 d1.md）。"


class Ctx:
    def __init__(self, target: Path):
        self.target = target
        sys.path.insert(0, str(target))
        from agentlab.rag import answer as mod  # noqa: PLC0415

        self.mod = mod
        self.answer = mod.answer
        self.REFUSE = mod.REFUSE
        assert isinstance(self.REFUSE, str) and self.REFUSE.strip(), "REFUSE 不是非空字符串"

    def reset(self, reply: str = REPLY) -> None:
        self.mod.llm.reply = reply
        self.mod.llm.calls.clear()

    def calls(self) -> int:
        return len(self.mod.llm.calls)

    def go(self, question: str = "端口是多少", top_score: float = 0.9, chunks=None):
        self.reset(getattr(self, "_reply", REPLY))
        out = self.answer(question, top_score, chunks if chunks is not None else [CHUNK])
        assert isinstance(out, tuple) and len(out) == 2, (
            f"answer() 返回了 {type(out).__name__}（{out!r}），应为 (文本, 原因) 二元组"
        )
        text, reason = out
        assert reason in REASONS, (
            f"原因 {reason!r} 不在白名单 {sorted(REASONS)} 里——"
            "三种原因是对外报指标用的字段，多一个值会让统计脚本静默漏数"
        )
        return text, reason


# ---------- 第一层：硬门槛 ----------
def c1_empty_chunks(ctx: Ctx) -> str:
    text, reason = ctx.go("端口是多少", 0.9, [])
    assert reason == "refused_low_score", f"空 chunks 返回 {reason}，应为 refused_low_score"
    assert ctx.calls() == 0, (
        f"空 chunks 仍然调了 {ctx.calls()} 次模型。硬门槛的价值就是「花钱之前拦住」——"
        "既然证据为空，调模型只能得到一段自信的编造"
    )
    assert text == ctx.REFUSE, "拒答文案不是 REFUSE 常量"
    return "空证据 → 拒答，零模型调用"


def c2_low_score(ctx: Ctx) -> str:
    text, reason = ctx.go("端口是多少", 0.0)
    assert reason == "refused_low_score", f"分数 0.0 返回 {reason}"
    assert ctx.calls() == 0, f"分数 0.0 仍然调了 {ctx.calls()} 次模型"
    return "分数 0.0 → 拒答，零模型调用"


def c3_boundary_pass(ctx: Ctx) -> str:
    """阈值是 `<` 不是 `<=`：正好 0.35 应该放行。

    这条看着吹毛求疵，但它区分两种实现——`top_score <= 0.35` 会让「刚好踩线」的
    样本全被拒，而这类样本在分布里往往是最多的一档（分数量化到 0.05 时）。
    """
    ctx._reply = REPLY
    _, reason = ctx.go("端口是多少", THRESHOLD, [CHUNK])
    assert reason != "refused_low_score", (
        f"top_score 正好 {THRESHOLD} 被判拒答（reason={reason}）——"
        "门槛应写成 `< {THRESHOLD}`，不是 `<=`。边界挪一格不报错，只是多拒一档"
    )
    return f"边界 {THRESHOLD} 放行 → {reason}"


def c4_just_below(ctx: Ctx) -> str:
    ctx._reply = REPLY
    _, reason = ctx.go("端口是多少", 0.34, [CHUNK])
    assert reason == "refused_low_score", (
        f"top_score=0.34 返回 {reason}，应被硬门槛拦住——"
        "门槛太低等于没有门槛，拒答全靠模型自觉"
    )
    return "0.34 → 拒答"


# ---------- 第二层：模型出口 ----------
def c5_model_refuse_phrase(ctx: Ctx) -> str:
    ctx._reply = "资料中没有相关信息。"
    text, reason = ctx.go("端口是多少", 0.9)
    assert reason == "refused_by_model", f"模型说「资料中没有」却返回 {reason}"
    assert text == ctx.REFUSE, "转成拒答时文案应该统一成 REFUSE，不然前端要认两句话"
    return "模型说没有 → 归一成拒答"


def c6_model_refuse_alt(ctx: Ctx) -> str:
    ctx._reply = "这个问题我无法回答。"
    _, reason = ctx.go("端口是多少", 0.9)
    assert reason == "refused_by_model", (
        f"模型说「无法回答」却返回 {reason}——只认一个短语的实现会漏掉另一批拒答，"
        "于是拒答率被低估"
    )
    return "另一个拒答说法也能识别"


def c7_answered(ctx: Ctx) -> str:
    ctx._reply = REPLY
    text, reason = ctx.go("端口是多少", 0.9)
    assert reason == "answered", f"正常回答返回 {reason}"
    assert text == REPLY, f"返回文本被动过：{text!r} ≠ {REPLY!r}"
    return "正常回答原样返回"


# ---------- 两层都要有 ----------
def c8_reasons_distinct(ctx: Ctx) -> str:
    ctx._reply = REPLY
    _, low = ctx.go("端口是多少", 0.0)
    ctx._reply = "资料中没有相关信息。"
    _, by_model = ctx.go("端口是多少", 0.9)
    assert low != by_model, (
        f"两种拒答用了同一个原因 {low!r}——原因字段是为了分开统计"
        "「门槛拦下多少」和「模型自己拒了多少」，合成一个就失去了诊断能力"
    )
    return f"{low} ≠ {by_model}"


def c9_text_identical(ctx: Ctx) -> str:
    ctx._reply = REPLY
    a, _ = ctx.go("端口是多少", 0.0)
    ctx._reply = "资料中没有相关信息。"
    b, _ = ctx.go("端口是多少", 0.9)
    assert a == b == ctx.REFUSE, (
        f"两种拒答的文案不一致：{a!r} vs {b!r}。"
        "对外只有一种「拒答」，用户不该看到两种说法"
    )
    return "两句拒答文案一致"


def c10_model_sees_rule(ctx: Ctx) -> str:
    ctx._reply = REPLY
    ctx.go("端口是多少", 0.9)
    assert ctx.calls() == 1, f"正常路径应该调 1 次模型，实际 {ctx.calls()} 次"
    msgs = ctx.mod.llm.calls[0]
    assert isinstance(msgs, list) and len(msgs) >= 2, (
        f"传给模型的是 {type(msgs).__name__}（{msgs!r}），应为带 system + user 的消息列表"
    )
    assert msgs[0].get("role") == "system", "第一条不是 system——拒答规则没有位置可放"
    assert "没有" in str(msgs[0].get("content", "")), (
        "system 段里没有「没有」这类拒答规则，第二层就没有出口，模型只能尽力回答"
    )
    user = " ".join(str(m.get("content", "")) for m in msgs if m.get("role") == "user")
    assert "端口" in user, f"user 段里找不到问题原文：{user[:80]!r}"
    return "system 带拒答规则，user 带问题"


# ---------- 稳健 ----------
def c11_empty_question(ctx: Ctx) -> str:
    ctx._reply = ctx.REFUSE
    _, reason = ctx.go("", 0.9)
    assert reason in REASONS, f"空问题崩了或返回非法原因 {reason!r}"
    return f"空问题 → {reason}"


def c12_empty_reply(ctx: Ctx) -> str:
    """模型返回空串 = 它什么都没答，不能记成 answered。"""
    ctx._reply = ""
    text, reason = ctx.go("端口是多少", 0.9)
    assert reason != "answered" or text.strip(), (
        "模型返回空串却记成 answered——通过率会把这个算成一次成功，"
        "而用户看到的是空白。空回复必须算拒答（或算失败），不能算答好"
    )
    return f"空回复 → {reason}"


def c13_shape(ctx: Ctx) -> str:
    ctx._reply = REPLY
    text, reason = ctx.go("端口是多少", 0.9)
    assert isinstance(text, str) and isinstance(reason, str), "返回的两项不都是 str"
    return "返回 (str, str)"


CHECKS = [
    ("空 chunks 直接拒答且不调模型", c1_empty_chunks),
    ("分数过低直接拒答", c2_low_score),
    ("边界 0.35 放行", c3_boundary_pass),
    ("0.34 被拦住", c4_just_below),
    ("模型说没有就转成拒答", c5_model_refuse_phrase),
    ("另一个拒答说法也认", c6_model_refuse_alt),
    ("正常回答原样返回", c7_answered),
    ("两种拒答原因可区分", c8_reasons_distinct),
    ("两句拒答文案一致", c9_text_identical),
    ("模型看到拒答规则", c10_model_sees_rule),
    ("空问题不崩", c11_empty_question),
    ("模型返回空串不算答好", c12_empty_reply),
    ("返回 (str, str)", c13_shape),
]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="判 P2-10 的拒答两层")
    ap.add_argument("--target", default=".", help="项目根目录（含 agentlab/）")
    args, rest = ap.parse_known_args()

    target = Path(args.target).expanduser().resolve()
    if not (target / "agentlab" / "rag" / "answer.py").is_file():
        return exit_missing(
            f"× 在 {target} 下没找到 agentlab/rag/answer.py",
            "  用 --target 指到项目根目录",
            "  CONTRACT §1 要求 answer() 与 REFUSE 在这里",
        )
    try:
        ctx = Ctx(target)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return exit_missing(f"× 导入失败：{type(exc).__name__}: {exc}")

    return run_all(
        "P2-10 判分 · 拒答两层",
        CHECKS,
        ctx,
        argv=rest,
        subtitle=f"目标 {target}",
        footer=(
            "注意：这里判「两层都在且顺序对」。\n"
            "      阈值该定多少、会不会过度拒答，必须用 W09 的 answerable/unanswerable 集跑分布，离线判不了。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
