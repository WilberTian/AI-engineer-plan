"""P1-13 判分器：判**你的** evals/run_eval.py 是否符合 CONTRACT.md。

    python3 labs/p1-13/harness/run_checks.py --script ~/code/agentlab/evals/run_eval.py

两层判分：

1. `judge(case, res)` 是纯函数 —— 直接喂假 res，判据对不对，8 条
2. 端到端 —— 用一个**假 agentlab** 替掉真模型，把你的 runner 当命令行真跑一遍，
   判「通过率 / 分组 / 失败 ID / 退出码 / 输出文件」这五件事，7 条

为什么端到端也要判：卡里的验收是「一条命令跑完，退出码非 0 时能接 CI」。
只判 judge 等于没判 runner —— runner 的价值恰恰在「可重复、有输出文件」。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "_shared"))
from checkkit import exit_missing, run_all  # noqa: E402

# ---------- 假 agentlab：替读者项目里的真实模块，让 runner 不碰模型 ----------

FAKE_AGENTLAB = {
    "__init__.py": "",
    "config.py": 'PRIMARY = "fake-model"\nBACKUP = "fake-model"\n',
    "llm.py": (
        '"""判分用假 LLM：不联网、不花钱、结果可复现。"""\n'
        "class LLM:\n"
        "    def __init__(self, model=None, *a, **kw):\n"
        "        self.model = model\n"
    ),
    "tools.py": (
        "class _Empty:\n"
        "    def specs(self):\n"
        "        return []\n"
        "    def names(self):\n"
        "        return []\n"
        "def build_registry():\n"
        "    return _Empty()\n"
    ),
    "loop.py": (
        '"""判分用假 loop：按 task 文本决定返回什么，不调模型。"""\n'
        "from dataclasses import dataclass, field\n"
        "\n"
        "@dataclass\n"
        "class Step:\n"
        "    idx: int\n"
        "    kind: str\n"
        "    name: str = ''\n"
        "    result: str = ''\n"
        "\n"
        "@dataclass\n"
        "class RunResult:\n"
        "    status: str\n"
        "    answer: str\n"
        "    steps: list = field(default_factory=list)\n"
        "    tool_calls: int = 0\n"
        "    elapsed_ms: float = 0.0\n"
        "    messages: list = field(default_factory=list)\n"
        "\n"
        "def run(task, llm=None, registry=None, **kw):\n"
        "    if 'BOOM' in task:\n"
        "        raise RuntimeError('模拟一次崩溃：判分要看单条失败会不会中断整轮')\n"
        "    return RunResult(\n"
        "        status='done',\n"
        "        answer='回答：' + task,\n"
        "        steps=[Step(idx=0, kind='tool', name='read_file', result='ok')],\n"
        "        tool_calls=1,\n"
        "        elapsed_ms=1.0,\n"
        "    )\n"
    ),
}

# 三条 case：两条应当过，一条会崩溃。凡是「模型」都能判定，不依赖 reader 的实现。
CASES = [
    {"id": "c1", "input": "说一句话", "tags": ["basic"], "expect": {"must_contain": ["回答"]}},
    {"id": "c2", "input": "说两句话", "tags": ["basic"], "expect": {"must_contain": ["回答"]}},
    {"id": "c3", "input": "BOOM", "tags": ["crash"], "expect": {}},
]
CASES_ALL_PASS = [c for c in CASES if "BOOM" not in c["input"]]


# ---------- 假 res：喂给 judge() ----------

class _Step:
    def __init__(self, name: str = "read_file", kind: str = "tool"):
        self.name, self.kind = name, kind


class _Res:
    def __init__(self, status="done", answer="答", steps=None, tool_calls=1):
        self.status = status
        self.answer = answer
        self.steps = steps if steps is not None else [_Step()]
        self.tool_calls = tool_calls
        self.elapsed_ms = 1.0
        self.messages = []


class Ctx:
    def __init__(self, judge, script: Path, workdir: Path):
        self.judge = judge
        self.script = script
        self.workdir = workdir
        self._e2e: dict = {}        # tag → 一次端到端结果，避免每条检查都重跑 subprocess

    def verdict(self, case: dict, res: _Res) -> tuple[bool, str]:
        out = self.judge(case, res)
        assert isinstance(out, tuple) and len(out) == 2, f"judge 应返回 (bool, str)，实际 {type(out).__name__}"
        passed, reason = out
        assert isinstance(passed, bool), f"judge 第一个返回值不是 bool，是 {type(passed).__name__}"
        assert isinstance(reason, str), f"judge 第二个返回值不是 str，是 {type(reason).__name__}"
        return passed, reason

    def e2e(self, cases: list[dict], tag: str) -> dict:
        """真跑一次 runner，返回 {rc, stdout, out_json}。"""
        if tag in self._e2e:
            return self._e2e[tag]
        d = self.workdir / tag
        d.mkdir(exist_ok=True)
        cases_path = d / "cases.jsonl"
        cases_path.write_text(
            "\n".join(json.dumps(c, ensure_ascii=False) for c in cases) + "\n", encoding="utf-8"
        )
        out_path = d / "result.json"
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self.workdir / "_fake")      # 假 agentlab 优先于读者项目
        env.pop("PYTHONHOME", None)
        r = subprocess.run(
            [sys.executable, str(self.script), "--cases", str(cases_path), "--out", str(out_path)],
            capture_output=True, text=True, env=env, cwd=str(d),
        )
        data = None
        if out_path.is_file():
            try:
                data = json.loads(out_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = None
        res = {"rc": r.returncode, "stdout": r.stdout + r.stderr, "out": data, "path": out_path}
        self._e2e[tag] = res
        return res


# ---------- judge() 的 8 条 ----------

def c1_ok(ctx: Ctx) -> str:
    passed, reason = ctx.verdict({"expect": {}}, _Res())
    assert passed is True, f"全部满足时应通过，实际 False，reason={reason!r}"
    return f"reason={reason!r}"


def c2_status(ctx: Ctx) -> str:
    passed, reason = ctx.verdict({"expect": {}}, _Res(status="max_steps"))
    assert passed is False, "status != done 时判通过了——这是最贵的假分数"
    assert "max_steps" in reason, f"理由里没写实际状态，看不出为什么红：{reason!r}"
    return reason[:40]


def c3_missing_tool(ctx: Ctx) -> str:
    passed, reason = ctx.verdict({"expect": {"tools": ["search_notes"]}},
                                 _Res(steps=[_Step("read_file")]))
    assert passed is False, "该调的工具没调，却判通过了"
    assert "search_notes" in reason, f"理由里没说是哪个工具缺了：{reason!r}"
    return reason[:50]


def c4_tool_budget(ctx: Ctx) -> str:
    passed, reason = ctx.verdict({"expect": {"max_tool_calls": 2}}, _Res(tool_calls=5))
    assert passed is False, "工具调用超上限却判通过了（成本失控就是从这里开始的）"
    return reason[:50]


def c5_must_contain(ctx: Ctx) -> str:
    passed, reason = ctx.verdict({"expect": {"must_contain": ["北京"]}}, _Res(answer="上海"))
    assert passed is False, "must_contain 缺失却判通过了"
    assert "北京" in reason, f"理由里没写缺哪个词：{reason!r}"
    return reason[:50]


def c6_must_not_contain(ctx: Ctx) -> str:
    passed, reason = ctx.verdict({"expect": {"must_not_contain": ["抱歉"]}},
                                 _Res(answer="抱歉，我不知道"))
    assert passed is False, "must_not_contain 出现了却判通过了"
    return reason[:50]


def c7_case_insensitive(ctx: Ctx) -> str:
    passed, _ = ctx.verdict({"expect": {"must_contain": ["beijing"]}}, _Res(answer="Beijing 天气晴"))
    assert passed is True, "must_contain 应大小写不敏感（手册 p1-13 的做法是双方 lower）"
    passed2, _ = ctx.verdict({"expect": {"must_not_contain": ["secret"]}},
                             _Res(answer="This is SECRET"))
    assert passed2 is False, "must_not_contain 应大小写不敏感"
    return "两边都大小写不敏感"


def c8_ok_reason(ctx: Ctx) -> str:
    _, reason = ctx.verdict({"expect": {"must_contain": ["答"]}}, _Res())
    assert reason.strip(), "通过时 reason 是空的——排查时你只能看到 PASS，不知道过了什么"
    return reason[:40]


# ---------- 端到端的 7 条 ----------

def c9_writes_file(ctx: Ctx) -> str:
    e = ctx.e2e(CASES, "mixed")
    assert e["out"] is not None, (
        f"没拿到可解析的输出 JSON（--out 指定的文件）\n"
        f"         退出码 {e['rc']}，输出尾部：{e['stdout'][-300:]!r}"
    )
    assert "summary" in e["out"], f"输出 JSON 缺 summary，实际顶层键 {sorted(e['out'])}"
    return f"{e['path'].name} 可解析"


def c10_summary(ctx: Ctx) -> str:
    s = ctx.e2e(CASES, "mixed")["out"]["summary"]
    for k in ("n", "passed", "rate", "failures", "by_tag"):
        assert k in s, f"summary 缺 {k}，实际键 {sorted(s)}"
    assert s["n"] == 3, f"summary.n={s['n']}，实际跑了 3 条"
    assert s["passed"] == 2, f"summary.passed={s['passed']}，应为 2（c1/c2 过，c3 崩）"
    assert abs(float(s["rate"]) - 2 / 3) < 0.01, f"summary.rate={s['rate']}，应为 0.667"
    return f"n={s['n']} passed={s['passed']} rate={s['rate']}"


def c11_failures(ctx: Ctx) -> str:
    f = ctx.e2e(CASES, "mixed")["out"]["summary"]["failures"]
    assert f == ["c3"], f"failures={f}，应只列 c3"
    return f"failures={f}"


def c12_by_tag(ctx: Ctx) -> str:
    t = ctx.e2e(CASES, "mixed")["out"]["summary"]["by_tag"]
    assert set(t) == {"basic", "crash"}, f"by_tag 的键是 {sorted(t)}，应为 basic/crash"
    assert str(t["basic"]).replace(" ", "") == "2/2", f"basic 组={t['basic']}，应为 2/2"
    assert str(t["crash"]).replace(" ", "") == "0/1", f"crash 组={t['crash']}，应为 0/1"
    return f"{t}"


def c13_result_fields(ctx: Ctx) -> str:
    rs = ctx.e2e(CASES, "mixed")["out"].get("results")
    assert isinstance(rs, list) and len(rs) == 3, f"results 应为 3 条，实际 {type(rs).__name__}/{len(rs or [])}"
    need = {"id", "passed", "reason", "status", "tool_calls", "latency_ms", "answer", "tags"}
    missing = need - set(rs[0])
    assert not missing, f"results 每条缺字段 {sorted(missing)}，实际 {sorted(rs[0])}"
    long = [r["id"] for r in rs if len(str(r["answer"])) > 500]
    assert not long, f"这些 case 的 answer 没截断：{long}（手册做法是只落前 300 字）"
    return "8 个字段齐，answer 已截断"


def c14_crash_isolated(ctx: Ctx) -> str:
    rs = ctx.e2e(CASES, "mixed")["out"]["results"]
    c3 = next((r for r in rs if r["id"] == "c3"), None)
    assert c3 is not None, "崩溃的 c3 在 results 里消失了——单条崩掉就中断了整轮"
    assert c3["passed"] is False, f"c3 崩了却算通过：{c3}"
    assert c3["status"] == "error", f"c3.status={c3['status']!r}，应为 'error'"
    assert c3["reason"].strip(), "c3 的 reason 是空的，排查时不知道崩在哪"
    return "崩溃只影响自己那条"


def c15_exit_nonzero(ctx: Ctx) -> str:
    rc = ctx.e2e(CASES, "mixed")["rc"]
    assert rc != 0, "有失败案例时退出码是 0 —— 接不了 CI，回归全靠人肉盯"
    return f"exit={rc}"


def c16_exit_zero(ctx: Ctx) -> str:
    rc = ctx.e2e(CASES_ALL_PASS, "allpass")["rc"]
    assert rc == 0, f"全部通过时退出码是 {rc}，应等于 0"
    return "全通过 exit=0"


CHECKS = [
    ("judge：全满足返回 True", c1_ok),
    ("judge：status 非 done 判红", c2_status),
    ("judge：该调的工具没调判红", c3_missing_tool),
    ("judge：工具调用超上限判红", c4_tool_budget),
    ("judge：must_contain 缺失判红", c5_must_contain),
    ("judge：must_not_contain 出现判红", c6_must_not_contain),
    ("judge：关键词大小写不敏感", c7_case_insensitive),
    ("judge：通过时 reason 非空", c8_ok_reason),
    ("端到端：写出可解析的结果 JSON", c9_writes_file),
    ("端到端：summary 的 n/passed/rate", c10_summary),
    ("端到端：failures 列出失败 id", c11_failures),
    ("端到端：by_tag 分组通过率", c12_by_tag),
    ("端到端：results 字段与截断", c13_result_fields),
    ("端到端：单条崩掉不中断整轮", c14_crash_isolated),
    ("端到端：有失败时退出码非 0", c15_exit_nonzero),
    ("端到端：全通过时退出码 0", c16_exit_zero),
]


def build_fake(tmp: Path) -> Path:
    pkg = tmp / "agentlab"
    pkg.mkdir(parents=True, exist_ok=True)
    for name, text in FAKE_AGENTLAB.items():
        (pkg / name).write_text(text, encoding="utf-8")
    return tmp


def load_runner(script: Path, fake_dir: Path):
    sys.path.insert(0, str(fake_dir))           # 让 run_eval.py 的 import 落到假 agentlab
    spec = importlib.util.spec_from_file_location("run_eval_under_test", script)
    mod = importlib.util.module_from_spec(spec)
    # 必须先登记再 exec：@dataclass 会去 sys.modules 里找 cls.__module__，没登记就 AttributeError
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser(description="判 P1-13 的 run_eval.py 是否符合 CONTRACT.md")
    ap.add_argument("--script", default="evals/run_eval.py", help="你的 run_eval.py 路径")
    args, rest = ap.parse_known_args()

    script = Path(args.script).expanduser().resolve()
    if not script.is_file():
        return exit_missing(
            f"× 找不到 {script}",
            "  用 --script 指到你的 runner，例：--script ~/code/agentlab/evals/run_eval.py",
        )

    workdir = Path(tempfile.mkdtemp(prefix="p1-13-lab-"))
    fake_dir = build_fake(workdir / "_fake")

    try:
        mod = load_runner(script, fake_dir)
    except Exception as exc:
        print(f"× 导入 {script.name} 失败：{type(exc).__name__}: {exc}")
        print("  CONTRACT §1 要求模块级存在 judge(case, res)")
        traceback.print_exc()
        return 2

    judge = getattr(mod, "judge", None)
    if judge is None:
        return exit_missing(
            f"× {script.name} 里没有模块级函数 judge(case, res)",
            "  CONTRACT §1：判据必须是纯函数，才能被单独验证",
        )

    return run_all(
        f"P1-13 判分 · 脚本 {script}",
        CHECKS,
        Ctx(judge, script, workdir),
        argv=rest,
        subtitle="端到端部分用假 agentlab 替掉真模型，不联网、不花钱",
        footer=(
            "注意：判的是「runner 是否可重复、有输出、能接 CI」，不是「你的 prompt 好不好」。\n"
            "      后者要靠 eval_results/*.json 前后对比，人看。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
