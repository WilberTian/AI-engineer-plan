"""P1-2 判分器：判**你的** schema.py 是否符合 CONTRACT.md。

    python3 labs/p1-2/harness/run_checks.py                 # 默认在 ./src 找 agentlab/
    python3 labs/p1-2/harness/run_checks.py --target <dir>  # 指定 src 目录

需要 pydantic（你项目里本来就有）。没装会直接提示，不会假装通过。

判的是「业务规则有没有真的生效」，不是「抄得像不像」。
所以第 7、8 条专门打两个方向：该拒的必须拒，该放的必须放。
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "_shared"))
from checkkit import exit_missing, run_all  # noqa: E402


class Ctx:
    def __init__(self, Answer: Any, Citation: Any, ve: type[Exception]):
        self.Answer = Answer
        self.Citation = Citation
        self.ValidationError = ve

    def cit(self, **kw):
        base = {"doc_id": "d1", "quote": "原文片段"}
        base.update(kw)
        return self.Citation(**base)

    def rejects(self, label: str, **fields) -> str:
        """断言某组数据必须被拒，且报错能定位到字段。"""
        try:
            got = self.Answer(**fields)
        except self.ValidationError as exc:
            locs = [e.get("loc") for e in exc.errors()]
            assert any(loc for loc in locs), f"{label} 被拒了，但 loc 为空——定位不到字段"
            return f"{label} → 拒（loc={locs[0]}）"
        raise AssertionError(
            f"{label} 没有被拒，实际得到 answer={getattr(got, 'answer', None)!r} "
            f"citations={[c.doc_id for c in getattr(got, 'citations', [])]}\n"
            "         这条是卡里验收明写的坏数据，必须抛 ValidationError"
        )

    def accepts(self, label: str, **fields) -> str:
        try:
            got = self.Answer(**fields)
        except self.ValidationError as exc:
            raise AssertionError(
                f"{label} 是合法数据，被误杀：{exc.errors()[0].get('msg')}\n"
                "         误杀合法数据比放过坏数据更难发现——模型每次拒答都会被拦下"
            ) from None
        return f"{label} → 过（refused={getattr(got, 'refused', None)}）"


# ---------- 检查 ----------

def c1_models(ctx: Ctx) -> str:
    from pydantic import BaseModel

    for cls in (ctx.Answer, ctx.Citation):
        assert issubclass(cls, BaseModel), f"{cls.__name__} 不是 BaseModel"
    return "Answer / Citation 都是 BaseModel"


def c2_valid(ctx: Ctx) -> str:
    return ctx.accepts("带引用的正常回答", answer="答", confidence="high", citations=[ctx.cit()])


def c3_confidence(ctx: Ctx) -> str:
    return ctx.rejects("confidence='very high'", answer="答", confidence="very high",
                       citations=[ctx.cit()])


def c4_quote_too_long(ctx: Ctx) -> str:
    # 传裸 dict 而不是 ctx.cit(...)：Citation 在这里会被构造，超长会先在构造处炸，
    # 炸点跑到 rejects() 外面就变成 ERR，测不到 Answer 的校验路径。
    return ctx.rejects("quote 超 300 字", answer="答", confidence="high",
                       citations=[{"doc_id": "d1", "quote": "x" * 301}])


def c5_doc_id_none(ctx: Ctx) -> str:
    return ctx.rejects("doc_id=None", answer="答", confidence="high",
                       citations=[{"doc_id": None, "quote": "q"}])


def c6_empty_with_refused_false(ctx: Ctx) -> str:
    """卡里验收第 3 组：citations 为空且 refused=false。"""
    return ctx.rejects("citations=[] 且 refused=False", answer="答", confidence="high",
                       citations=[], refused=False)


def c7_empty_default(ctx: Ctx) -> str:
    """同样的坏数据，但**不传** citations（走默认值）。

    这是最容易漏的一格：模型的真实输出里通常根本没有 citations 这个键。
    pydantic 的 field_validator 默认不校默认值，规则会整条失效（见 NOTES §4）。
    """
    return ctx.rejects("citations 不传 且 refused=False", answer="答", confidence="high")


def c8_refused_ok(ctx: Ctx) -> str:
    """明确拒答时没有引用是**合法**的。

    必须**显式传** `citations=[]`：不传的话 validator 根本不会跑，
    那条会「因为没执行而通过」，测不出字段顺序的坑（见 NOTES §4 第 2 条）。
    """
    return ctx.accepts("refused=True 且 citations=[]", answer="", confidence="low",
                       citations=[], refused=True)


def c9_refused_default(ctx: Ctx) -> str:
    got = ctx.Answer(answer="答", confidence="high", citations=[ctx.cit()])
    assert got.refused is False, f"refused 默认值是 {got.refused!r}，应为 False"
    return "refused 默认 False"


def c10_no_shared_list(ctx: Ctx) -> str:
    a = ctx.Answer(answer="a", confidence="high", citations=[ctx.cit()])
    b = ctx.Answer(answer="b", confidence="high", refused=True)
    assert a.citations is not b.citations, "两个实例共用同一个 citations 列表（缺 default_factory）"
    return "citations 各自独立，没有共享可变默认值"


def c11_json_schema(ctx: Ctx) -> str:
    try:
        s = ctx.Answer.model_json_schema()
    except AttributeError:
        raise AssertionError("Answer 没有 model_json_schema()（pydantic v1？本项目统一 v2）") from None
    props = s.get("properties") or {}
    for k in ("answer", "confidence", "citations", "refused"):
        assert k in props, f"schema 缺字段 {k}，实际 {sorted(props)}"
    assert "enum" in (props["confidence"] or {}), "schema 里 confidence 不是 enum —— 结构化输出时模型不受约束"
    return "schema 四个字段齐全，confidence 是 enum"


def c12_locatable(ctx: Ctx) -> str:
    """所有坏数据的报错都要能指到字段，否则你 debug 时只能靠猜。"""
    cases = {
        "confidence": dict(answer="答", confidence="nope", citations=[ctx.cit()]),
        "quote": dict(answer="答", confidence="high", citations=[{"doc_id": "d1", "quote": ""}]),
        "doc_id": dict(answer="答", confidence="high", citations=[{"quote": "q"}]),
    }
    out = []
    for label, fields in cases.items():
        try:
            ctx.Answer(**fields)
        except ctx.ValidationError as exc:
            loc = str([e.get("loc") for e in exc.errors()])
            assert label in loc, f"{label} 的报错定位不到该字段：loc={loc}"
            out.append(label)
        else:
            raise AssertionError(f"{label} 的坏数据没被拒")
    return "三类报错都定位到字段：" + "/".join(out)


CHECKS = [
    ("Answer/Citation 是 BaseModel", c1_models),
    ("合法数据能通过", c2_valid),
    ("confidence 非法值被拒", c3_confidence),
    ("quote 超长被拒", c4_quote_too_long),
    ("doc_id=None 被拒", c5_doc_id_none),
    ("citations=[] 且 refused=False 被拒", c6_empty_with_refused_false),
    ("citations 不传也受同一规则约束", c7_empty_default),
    ("refused=True 时无引用应通过", c8_refused_ok),
    ("refused 默认 False", c9_refused_default),
    ("citations 不共享默认列表", c10_no_shared_list),
    ("model_json_schema 可用", c11_json_schema),
    ("报错能定位到字段", c12_locatable),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="判 P1-2 的 schema.py 是否符合 CONTRACT.md")
    ap.add_argument("--target", default="src", help="含 agentlab/ 的目录，默认 ./src")
    args, rest = ap.parse_known_args()

    try:
        from pydantic import ValidationError
    except ImportError:
        return exit_missing(
            "× 当前 Python 里没有 pydantic，判不了。",
            "  你的项目用 uv 管理的话：uv run python labs/p1-2/harness/run_checks.py --target <dir>",
        )

    target = Path(args.target).expanduser().resolve()
    if not (target / "agentlab").is_dir():
        return exit_missing(
            f"× 在 {target} 下没找到 agentlab/",
            "  用 --target 指到你的 src 目录，例：--target ~/code/agentlab-project/src",
        )
    sys.path.insert(0, str(target))

    try:
        from agentlab.schema import Answer, Citation
    except Exception as exc:
        print(f"× 导入失败：{type(exc).__name__}: {exc}")
        print("  CONTRACT §1 要求 agentlab.schema 提供 Answer 与 Citation")
        traceback.print_exc()
        return 2

    return run_all(
        f"P1-2 判分 · 目标 {target}",
        CHECKS,
        Ctx(Answer, Citation, ValidationError),
        argv=rest,
        footer=(
            "注意：这 12 条判的是「业务规则有没有真的生效」。\n"
            "      第 7、8 条是很多实现的盲区（默认值不走 validator / 字段顺序取不到后面的值），\n"
            "      手册当前的参考实现也栽在这两条上——见 NOTES §4。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
