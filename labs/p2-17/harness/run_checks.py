"""P2-17 判分：用户记忆的写、读、落盘。

被判对象 `agentlab/memory.py`：`Memory` / `upsert` / `recall` / `load` / `save`。

四件事，对应卡里四层评估：

1. **写对**：同一键再写是覆盖、同值不产生噪音、冲突后只有一条
2. **读对**：按需注入，不是全量塞进 system
3. **落盘**：跨进程还能读到（不是内存里）
4. **中文**：中文查询没有空格，`query.split()` 这条路走不通

第 4 条参考实现是红的。它不影响英文，也不报错，只会让中文用户永远「没有记忆」。

    python3 labs/p2-17/harness/run_checks.py --target ~/code/agentlab-project
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "_shared"))
from checkkit import exit_missing, run_all  # noqa: E402


class Ctx:
    def __init__(self, target: Path):
        self.target = target
        sys.path.insert(0, str(target))
        from agentlab import memory as mod  # noqa: PLC0415

        self.mod = mod
        self.Memory = mod.Memory

    def m(self, key: str, value: str, kind: str = "fact", source: str = "s1"):
        return self.Memory(key=key, value=value, kind=kind, source=source)


# ---------- 写：三种结果 ----------
def c1_added(ctx: Ctx) -> str:
    store: dict = {}
    r = ctx.mod.upsert(store, ctx.m("personal.diet", "不吃辣"))
    assert r == "added", f"新键应返回 added，实为 {r!r}"
    assert "personal.diet" in store, "upsert 之后 store 里没有这条"
    return "新键 → added"


def c2_noop(ctx: Ctx) -> str:
    store: dict = {}
    ctx.mod.upsert(store, ctx.m("personal.diet", "不吃辣"))
    r = ctx.mod.upsert(store, ctx.m("personal.diet", "不吃辣", source="s2"))
    assert r == "noop", f"同值重复写入应返回 noop，实为 {r!r}"
    return "同值 → noop"


def c3_updated(ctx: Ctx) -> str:
    store: dict = {}
    ctx.mod.upsert(store, ctx.m("personal.diet", "不吃辣"))
    r = ctx.mod.upsert(store, ctx.m("personal.diet", "微辣可以", source="s2"))
    assert r == "updated", f"改主意应返回 updated，实为 {r!r}"
    return "改值 → updated"


def c4_conflict_single_row(ctx: Ctx) -> str:
    """冲突后只保留一条。并存两份的话，注入时两条会同时进上下文，模型自己打架。"""
    store: dict = {}
    ctx.mod.upsert(store, ctx.m("personal.diet", "不吃辣"))
    ctx.mod.upsert(store, ctx.m("personal.diet", "微辣可以", source="s2"))
    assert len(store) == 1, f"同键写两次后 store 有 {len(store)} 条——并存的旧值会一起被注入"
    assert store["personal.diet"].value == "微辣可以", f"留下的不是新值：{store['personal.diet'].value}"
    return "同键只有一条，且是新值"


def c5_conflict_counts_once(ctx: Ctx) -> str:
    """卡里要求「updated 计数为 1 而不是两条并存」——所以得能数出来。"""
    store: dict = {}
    res = [ctx.mod.upsert(store, ctx.m("k", v)) for v in ("a", "b", "c")]
    assert res == ["added", "updated", "updated"], f"三次写入的返回值应为 added/updated/updated，实为 {res}"
    assert res.count("updated") == 2, "更新次数要能被调用方数出来（这就是冲突率）"
    return "更新次数可统计"


def c6_source_tracked(ctx: Ctx) -> str:
    """每条要记住是哪次会话写进来的，出问题才能回溯。"""
    store: dict = {}
    ctx.mod.upsert(store, ctx.m("k", "v", source="session-42"))
    assert store["k"].source == "session-42", f"source 丢了：{store['k'].source}"
    return "保留 source"


def c7_kind_preserved(ctx: Ctx) -> str:
    store: dict = {}
    ctx.mod.upsert(store, ctx.m("k", "v", kind="preference"))
    assert store["k"].kind == "preference", f"kind 丢了：{store['k'].kind}"
    return "保留 kind"


# ---------- 落盘 ----------
def c8_roundtrip(ctx: Ctx) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "memory.json"
        store: dict = {}
        ctx.mod.upsert(store, ctx.m("family.father.doctor", "父亲的医生是李医生", kind="fact"))
        ctx.mod.save(p, store)
        back = ctx.mod.load(p)
        assert back == store, f"存盘再读回来不一致：{back} != {store}"
    return "存盘往返一致（含中文）"


def c9_load_missing(ctx: Ctx) -> str:
    """文件不存在当新用户，不该抛异常。"""
    with tempfile.TemporaryDirectory() as tmp:
        got = ctx.mod.load(Path(tmp) / "nope.json")
        assert got == {}, f"不存在的文件应返回空 dict，实为 {got!r}"
    return "文件不存在 → {}"


def c10_cross_process(ctx: Ctx) -> str:
    """卡里第 ① 条：开两个进程，第一个写、第二个读。这才是「真落盘」。"""
    tmpdir = tempfile.mkdtemp(prefix="p2-17-x-")
    mpath = Path(tmpdir) / "m.json"
    write = f'''
import sys
sys.path.insert(0, {str(ctx.target)!r})
from pathlib import Path
from agentlab.memory import Memory, upsert, load, save
p = Path({str(mpath)!r})
store = load(p)
upsert(store, Memory(key="personal.city", value="上海", kind="fact", source="s1"))
save(p, store)
'''
    read = f'''
import sys
sys.path.insert(0, {str(ctx.target)!r})
from pathlib import Path
from agentlab.memory import load
store = load(Path({str(mpath)!r}))
print("CITY=" + store["personal.city"].value if "personal.city" in store else "MISSING")
'''
    r1 = subprocess.run([sys.executable, "-c", write], capture_output=True, text=True)
    assert r1.returncode == 0, f"写入子进程失败：{r1.stderr}"
    r2 = subprocess.run([sys.executable, "-c", read], capture_output=True, text=True)
    assert "CITY=上海" in r2.stdout, (
        f"第二个进程没读到记忆（stdout={r2.stdout!r} stderr={r2.stderr!r}）——说明它只在内存里"
    )
    return "跨进程读到了"


# ---------- 读：按需注入 ----------
def c11_recall_chinese(ctx: Ctx) -> str:
    """中文查询没有空格，`query.split()` 切不出词。

    参考实现是这条红：`any(w in m.value for w in query.split())`，
    对「我不吃辣吗」这种连续中文，切出来只有一整串，于是永远不命中。
    """
    store: dict = {}
    ctx.mod.upsert(store, ctx.m("personal.diet", "不吃辣", kind="preference"))
    out = ctx.mod.recall(store, "我吃辣吗")
    assert out.strip(), (
        "中文查询什么都没召回——`query.split()` 对连续中文只会切出一个整串，\n"
        "          于是 `w in m.value` 永远为 False。中文场景要么分词，要么做双向子串匹配"
    )
    return f"召回：{out[:30]}"


def c12_recall_prefers_preference(ctx: Ctx) -> str:
    store: dict = {}
    ctx.mod.upsert(store, ctx.m("a.fact", "公司地址在张江", kind="fact"))
    ctx.mod.upsert(store, ctx.m("b.pref", "喜欢简洁回答", kind="preference"))
    out = ctx.mod.recall(store, "张江 简洁", k=2)
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert lines and "简洁" in lines[0], f"偏好应排在前面，实际顺序：{lines}"
    return "偏好排在前"


def c13_recall_k_limit(ctx: Ctx) -> str:
    store: dict = {}
    for i in range(8):
        ctx.mod.upsert(store, ctx.m(f"k{i}", f"关键词 alpha 的第 {i} 条"))
    out = ctx.mod.recall(store, "alpha", k=3)
    n = len([ln for ln in out.splitlines() if ln.strip()])
    assert n <= 3, f"k=3 却注入了 {n} 条——按需注入变成了全量塞"
    return f"k=3 注入 {n} 条"


def c14_recall_empty(ctx: Ctx) -> str:
    assert ctx.mod.recall({}, "任意") == "", "空库的召回应是空字符串，不是 None 或异常"
    return "空库 → 空串"


CHECKS = [
    ("新键写入返回 added", c1_added),
    ("同值重写返回 noop", c2_noop),
    ("改值返回 updated", c3_updated),
    ("冲突后只有一条且是新值", c4_conflict_single_row),
    ("更新次数可统计", c5_conflict_counts_once),
    ("保留 source 可回溯", c6_source_tracked),
    ("保留 kind", c7_kind_preserved),
    ("存盘往返一致（中文）", c8_roundtrip),
    ("文件不存在返回空库", c9_load_missing),
    ("跨进程能读到（真落盘）", c10_cross_process),
    ("中文查询能召回", c11_recall_chinese),
    ("偏好排在一般事实前", c12_recall_prefers_preference),
    ("按 k 限制注入条数", c13_recall_k_limit),
    ("空库召回空串", c14_recall_empty),
]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="判 P2-17 的用户记忆")
    ap.add_argument("--target", default=".", help="项目根目录（含 agentlab/）")
    args, rest = ap.parse_known_args()

    target = Path(args.target).expanduser().resolve()
    if not (target / "agentlab" / "memory.py").is_file():
        return exit_missing(
            f"× 在 {target} 下没找到 agentlab/memory.py",
            "  用 --target 指到项目根目录",
            "  CONTRACT §1 要求 Memory / upsert / recall / load / save 都在这个文件里",
        )
    try:
        ctx = Ctx(target)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return exit_missing(f"× 导入失败：{type(exc).__name__}: {exc}")

    return run_all(
        "P2-17 判分 · 用户记忆",
        CHECKS,
        ctx,
        argv=rest,
        subtitle=f"目标 {target}",
        footer=(
            "注意：这里判的是「写对、读对、真落盘」。\n"
            "      卡里第 ③ 条「能说出选这个格式的理由」判不了——那是你的判断，不是代码。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
