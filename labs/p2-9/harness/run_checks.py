"""P2-9 判分：引用编号对得上、覆盖率高不高。

被判对象 `agentlab/rag/cite.py`：`build_context(chunks)` + `check(answer, n_chunks)`。

引用机制的 bug 有个共同特征：**不报错，只是查不回去**。答案读起来完全正常，
点开引用跳到无关段落——用户不会告诉你，他下次就不点了。所以只能靠断言压。

    python3 labs/p2-9/harness/run_checks.py --target ~/code/agentlab-project
"""
from __future__ import annotations

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
        from agentlab.rag import cite as mod  # noqa: PLC0415

        self.mod = mod
        self.build_context = mod.build_context
        self.check = mod.check


CHUNKS = [
    ("notes/chunk-a.md", "分块起始接近 400 token，重叠 15%。"),
    ("notes/chunk-b.md", "重叠比例过高会让索引膨胀，通常 10–20% 足够。"),
    ("notes/chunk-c.md", "结构化分块保留标题层级，召回率更高。"),
]


# ---------- build_context：编号要对得上 ----------
def c1_numbering_from_one(ctx: Ctx) -> str:
    """编号从 1 开始——因为 system 里写的是「编号对应资料块序号」，人也是从 1 数的。"""
    out = ctx.build_context(CHUNKS)
    assert "[1]" in out, f"没有 [1] 编号：{out[:80]!r}"
    assert "[0]" not in out, f"出现了 [0]——从 0 开始编号，模型会引 [0]，而人读起来是错的"
    return "编号从 1 开始"


def c2_numbering_matches_count(ctx: Ctx) -> str:
    """几块资料就该有几个编号，一个不多一个不少。"""
    out = ctx.build_context(CHUNKS)
    for i in range(1, len(CHUNKS) + 1):
        assert f"[{i}]" in out, f"缺编号 [{i}]"
    assert f"[{len(CHUNKS) + 1}]" not in out, f"多出一个 [{len(CHUNKS) + 1}]"
    return f"3 块 → [1][2][3]"


def c3_source_in_context(ctx: Ctx) -> str:
    """每块要带来源路径，不然模型引了 [2] 你也查不回原文。"""
    out = ctx.build_context(CHUNKS)
    for src, _ in CHUNKS:
        assert src in out, f"上下文里丢了来源 {src}"
    return "每块带来源"


def c4_chunks_separated(ctx: Ctx) -> str:
    """块与块之间要隔开，否则模型会把两块当一段引。"""
    out = ctx.build_context(CHUNKS)
    assert "\n\n" in out, "块之间没有空行分隔"
    return "块间有空行"


def c5_empty_context(ctx: Ctx) -> str:
    out = ctx.build_context([])
    assert out.strip() == "", f"空资料应拼出空串，实为 {out!r}"
    return "空资料 → 空串"


# ---------- check：编号合法性 ----------
def c6_valid_cites(ctx: Ctx) -> str:
    r = ctx.check("分块 400 token 比较合适[1]。重叠 15% 足够[2]。", n_chunks=3)
    assert r.cited == [1, 2], f"引用的编号应提取为 [1,2]，实为 {r.cited}"
    assert r.invalid == [], f"合法编号被判非法：{r.invalid}"
    return f"cited={r.cited}"


def c7_out_of_range(ctx: Ctx) -> str:
    """引了不存在的编号 = 幻觉引用，必须判红。"""
    r = ctx.check("这个结论有依据[7]。", n_chunks=3)
    assert r.invalid == [7], f"[7] 超出了 3 块资料的范围，应判 invalid，实为 {r.invalid}"
    return "超范围编号判 invalid"


def c8_zero_cite_invalid(ctx: Ctx) -> str:
    """[0] 不存在（编号从 1 起），要判非法而不是「第 0 块」。"""
    r = ctx.check("这个结论有依据[0]。", n_chunks=3)
    assert r.invalid == [0], f"[0] 应判 invalid，实为 {r.invalid}"
    return "[0] 判 invalid"


def c9_dedupe(ctx: Ctx) -> str:
    r = ctx.check("A[1]。B[1] 也说了[2]。", n_chunks=3)
    assert r.cited == [1, 2], f"重复引用应去重，实为 {r.cited}"
    return "重复引用去重"


# ---------- check：覆盖率 ----------
def c10_uncited_detected(ctx: Ctx) -> str:
    r = ctx.check("分块大小应该设置成四百个 token 左右比较好用。重叠比例百分之十五就够了[1]。", n_chunks=3)
    assert len(r.uncited_sentences) == 1, f"应发现 1 句没标来源，实为 {r.uncited_sentences}"
    return "发现未引用句"


def c11_refusal_exempt(ctx: Ctx) -> str:
    """拒答句不需要引用——它是「我没找到」，没有来源可标。"""
    r = ctx.check("资料中没有相关信息，无法回答这个问题。", n_chunks=3)
    assert r.uncited_sentences == [], f"拒答句被当成未引用：{r.uncited_sentences}"
    return "拒答句豁免"


def c12_ok_flag(ctx: Ctx) -> str:
    # 注意句子要够长（>15 字），否则会先被手册的短句过滤掉，测不到 ok 判据
    good = ctx.check(
        "关于分块大小的结论是尽量设置成四百个 token 左右比较合适[1]。"
        "至于重叠比例，实践中百分之十五就已经足够用了。", n_chunks=3)
    assert len(good.uncited_sentences) == 1, f"用例该有 1 句未引用，实际 {len(good.uncited_sentences)} 句"
    assert good.ok is True, "只有 1 句未引用时 ok 应为 True（手册的宽松设计）"

    bad = ctx.check(
        "关于分块大小的结论是尽量设置成四百个 token 左右比较合适。"
        "关于重叠比例的结论是百分之十五就已经足够用了。"
        "关于结构化分块的结论是保留标题层级可以让召回率更高一些。", n_chunks=3)
    assert bad.ok is False, f"3 句全无引用时 ok 应为 False，实际未引用 {len(bad.uncited_sentences)} 句"
    return "ok 判据一致"


def c13_short_sentence_gap(ctx: Ctx) -> str:
    """手册用 `len(s) > 15` 过滤短句。14 字的结论句会被整句跳过——这是漏检。

    这一条判的是覆盖面：短句子也得查。参考实现是这条红。
    """
    r = ctx.check("Token 上限是8000", n_chunks=3)
    assert len(r.uncited_sentences) == 1, (
        f"14 字的结论句没被检查（uncited={r.uncited_sentences}）——\n"
        "          短句不等于不重要：「Token 上限是 8000」这种事实恰恰最需要引用"
    )
    return "短句也检查"


def c14_english_sentence(ctx: Ctx) -> str:
    """只按中文句号和换行切句，英文整段会算成一句，覆盖率失真。"""
    r = ctx.check("Chunking at 400 tokens works well. Overlap of 15% is enough. Structure matters.", n_chunks=3)
    assert len(r.uncited_sentences) == 3, (
        f"三句英文应算 3 句未引用，实际算成 {len(r.uncited_sentences)} 句——"
        "英文句号没被当作分句符，一整段只查一次"
    )
    return "英文句子也被切分"


CHECKS = [
    ("编号从 1 开始", c1_numbering_from_one),
    ("编号数量与资料块一致", c2_numbering_matches_count),
    ("每块带来源路径", c3_source_in_context),
    ("块之间有空行分隔", c4_chunks_separated),
    ("空资料拼出空串", c5_empty_context),
    ("合法引用能提取", c6_valid_cites),
    ("超范围编号判非法", c7_out_of_range),
    ("[0] 判非法", c8_zero_cite_invalid),
    ("重复引用去重", c9_dedupe),
    ("发现未引用句", c10_uncited_detected),
    ("拒答句豁免", c11_refusal_exempt),
    ("ok 判据一致", c12_ok_flag),
    ("短句也检查", c13_short_sentence_gap),
    ("英文句子也被切分", c14_english_sentence),
]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="判 P2-9 的引用机制")
    ap.add_argument("--target", default=".", help="项目根目录（含 agentlab/）")
    args, rest = ap.parse_known_args()

    target = Path(args.target).expanduser().resolve()
    if not (target / "agentlab" / "rag" / "cite.py").is_file():
        return exit_missing(
            f"× 在 {target} 下没找到 agentlab/rag/cite.py",
            "  用 --target 指到项目根目录",
            "  CONTRACT §1 要求 build_context / check / CiteCheck 都在这个文件里",
        )
    try:
        ctx = Ctx(target)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return exit_missing(f"× 导入失败：{type(exc).__name__}: {exc}")

    return run_all(
        "P2-9 判分 · 引用机制",
        CHECKS,
        ctx,
        argv=rest,
        subtitle=f"目标 {target}",
        footer=(
            "注意：这里判的是「编号对得上、覆盖率量得出来」。\n"
            "      判不了「模型会不会老老实实标注」——那要靠真实答案样本，离线做不到。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
