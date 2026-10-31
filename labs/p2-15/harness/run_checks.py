"""P2-15 判分：工具描述够不够模型决策用。

被判对象 `tools/search.json`。判的是**描述的可执行性**，不是文笔：
「何时用 / 何时别用 / 返回什么」三段缺一段，模型就只能靠名字猜。

这类检查全是静态的——描述写得好不好，最终要看模型选对率（P2-13 的指标）。
但「有没有写反例」是能判的，而它是选错率的最大单一原因。

    python3 labs/p2-15/harness/run_checks.py --target ~/code/agentlab-project
"""
from __future__ import annotations

import json
import re
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "_shared"))
from checkkit import exit_missing, run_all  # noqa: E402

MIN_DESC = 80
MAX_PARAMS = 6
# 「切在后端接口上」的命名痕迹
INTERFACE_SMELL = ("_by_", "get_", "list_", "chunk")
PLACEHOLDER = ("...", "…", "TODO", "待补")


class Ctx:
    def __init__(self, target: Path):
        self.path = target / "tools" / "search.json"
        raw = self.path.read_text(encoding="utf-8")
        self.raw = raw
        self.spec = json.loads(raw)
        if not isinstance(self.spec, dict):
            raise TypeError(f"顶层是 {type(self.spec).__name__}，不是 JSON 对象")
        self.desc = str(self.spec.get("description") or "")
        params = self.spec.get("parameters")
        self.params = params if isinstance(params, dict) else {}
        props = self.params.get("properties")
        self.props = props if isinstance(props, dict) else {}
        req = self.params.get("required")
        self.required = req if isinstance(req, list) else []


# ---------- 结构 ----------
def c1_parse(ctx: Ctx) -> str:
    return f"可解析，顶层是对象（{len(ctx.raw)} 字符）"


def c2_keys(ctx: Ctx) -> str:
    lack = [k for k in ("name", "description", "parameters") if k not in ctx.spec]
    assert not lack, f"缺顶层键 {lack}——这三个是模型能看到的全部信息，少一个等于没给"
    return "name / description / parameters 都在"


def c3_name(ctx: Ctx) -> str:
    name = str(ctx.spec.get("name") or "")
    assert name, "name 是空的"
    assert name == name.lower() and " " not in name, f"name={name!r} 应该是小写、无空格"
    assert re.fullmatch(r"[a-z][a-z0-9_]*", name), f"name={name!r} 含非常规字符"
    return f"name={name}"


# ---------- 名字没有按接口拆 ----------
def c4_no_interface_split(ctx: Ctx) -> str:
    name = str(ctx.spec.get("name") or "")
    hit = [s for s in INTERFACE_SMELL if s in name]
    assert not hit, (
        f"name={name!r} 含 {hit}——这是「照着后端接口切工具」的痕迹。\n"
        "          按接口切的后果：工具一多模型选错率立刻上升（公开评测里超过 100 个工具时\n"
        "          最先进模型也开始挑错）。标题、日期、来源都该收进 filters 参数，\n"
        "          不是一个接口一个工具"
    )
    return f"{name} 没有按接口拆"


# ---------- 描述三段 ----------
def c5_desc_length(ctx: Ctx) -> str:
    n = len(ctx.desc)
    assert n >= MIN_DESC, (
        f"description 只有 {n} 字（要求 ≥{MIN_DESC}）。"
        "「搜索文档库」这种长度只能靠名字猜——三段说明写不进 80 字"
    )
    return f"{n} 字"


def c6_when_to_use(ctx: Ctx) -> str:
    assert "何时用" in ctx.desc, (
        "description 里没有「何时用」——模型看不出触发条件，"
        "只能靠工具名联想，于是该搜的时候不搜、不该搜的时候乱搜"
    )
    return "写了触发条件"


def c7_when_not_to_use(ctx: Ctx) -> str:
    assert "何时别用" in ctx.desc, (
        "description 里没有「何时别用」（反例）。这是三段里最容易被省掉、也最值钱的一段：\n"
        "          没有它，「能直接回答却去查了一堆」这种浪费就管不住"
    )
    return "写了反例"


def c8_what_it_returns(ctx: Ctx) -> str:
    assert "返回" in ctx.desc, (
        "description 里没有「返回」——模型不知道能拿到什么，就无法判断要不要继续追查"
    )
    return "写了返回形态"


def c9_no_placeholder(ctx: Ctx) -> str:
    hit = [p for p in PLACEHOLDER if p in ctx.desc]
    assert not hit, f"description 里有占位符 {hit}——这段是要发给模型的，占位符会被原样注入"
    return "没有占位符"


# ---------- 参数 ----------
def c10_params_object(ctx: Ctx) -> str:
    assert ctx.params.get("type") == "object", (
        f"parameters.type={ctx.params.get('type')!r}，应为 'object'"
    )
    assert ctx.props, "parameters.properties 是空的——模型没有任何参数可填"
    return f"{len(ctx.props)} 个参数"


def c11_required(ctx: Ctx) -> str:
    assert ctx.required, "required 是空的——所有参数都可省，模型会漏填必要的那个"
    ghost = [r for r in ctx.required if r not in ctx.props]
    assert not ghost, (
        f"required 里写了 properties 中不存在的参数 {ghost}——"
        "调用时必然校验失败，而且是运行时才炸"
    )
    return f"required = {ctx.required}"


def c12_param_desc(ctx: Ctx) -> str:
    lack = [k for k, v in ctx.props.items()
            if not isinstance(v, dict) or not str(v.get("description") or "").strip()]
    assert not lack, (
        f"这些参数没有 description：{lack}。"
        "参数名本身就是歧义源（`query` 是关键词还是问句？），没有说明模型只能猜"
    )
    return f"{len(ctx.props)} 个参数都有说明"


# ---------- 收紧 ----------
def c13_closed(ctx: Ctx) -> str:
    assert ctx.params.get("additionalProperties") is False, (
        f"parameters.additionalProperties={ctx.params.get('additionalProperties')!r}，应为 false。\n"
        "          不收紧的话模型会自己发明参数（`top_k`、`lang`…），调用直接报非法参数"
    )
    return "参数空间已收紧"


def c14_few_params(ctx: Ctx) -> str:
    n = len(ctx.props)
    assert n <= MAX_PARAMS, (
        f"有 {n} 个参数（建议 ≤{MAX_PARAMS}）。参数越多，模型填错的组合爆炸——"
        "能用 filters 一个对象收住的，不要摊平成一堆顶层参数"
    )
    return f"{n} 个参数（≤{MAX_PARAMS}）"


CHECKS = [
    ("JSON 可解析且是对象", c1_parse),
    ("三个顶层键都在", c2_keys),
    ("name 是小写动词名", c3_name),
    ("name 没有按接口拆", c4_no_interface_split),
    ("描述够长", c5_desc_length),
    ("写了何时用", c6_when_to_use),
    ("写了何时别用", c7_when_not_to_use),
    ("写了返回形态", c8_what_it_returns),
    ("描述没有占位符", c9_no_placeholder),
    ("parameters 是对象且有属性", c10_params_object),
    ("required 非空且不指向不存在的参数", c11_required),
    ("每个参数都有说明", c12_param_desc),
    ("参数空间已收紧", c13_closed),
    ("参数不超过 6 个", c14_few_params),
]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="判 P2-15 的工具描述规格")
    ap.add_argument("--target", default=".", help="项目根目录（含 tools/）")
    args, rest = ap.parse_known_args()

    target = Path(args.target).expanduser().resolve()
    path = target / "tools" / "search.json"
    if not path.is_file():
        return exit_missing(
            f"× 在 {target} 下没找到 tools/search.json",
            "  用 --target 指到项目根目录",
            "  CONTRACT §1 要求工具的规格落在这里",
        )
    try:
        ctx = Ctx(target)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return exit_missing(f"× 读规格失败：{type(exc).__name__}: {exc}")

    return run_all(
        "P2-15 判分 · 工具描述规格",
        CHECKS,
        ctx,
        argv=rest,
        subtitle=f"目标 {path}",
        footer=(
            "注意：这里判「描述里有没有那三段」，判不了「模型会不会因此选对」。\n"
            "      后者要真跑（P2-13 的指标），而且要一个能对比的两版描述。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
