"""P3-13 判分：从 trace 挖失败样本的脚本。

被判对象 `evals/mine_failures.py`。判分器铺一份固定的 `logs/runs.jsonl`（9 条），
跑你的脚本，然后看 `evals/v2.jsonl` 里挖出了什么。

判的是三件事：
  1. 该挖的挖到了（四种失败信号各一次 + 未知类型也要收）
  2. 不该挖的没被挖（正常样本不许误报）
  3. `expected` 一律留空——让模型填 expected，等于让出题人自己批改

    python3 labs/p3-13/harness/run_checks.py --target ~/code/agentlab-project
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "_shared"))
sys.path.insert(0, str(HERE))
from checkkit import exit_missing, run_all  # noqa: E402
from logs_fixture import EXPECT_KINDS, HEALTHY, LOG_ROWS  # noqa: E402


class Ctx:
    """在临时沙箱里跑读者的脚本。

    为什么不直接在 `--target` 里跑：脚本按 CONTRACT 会写 `evals/v2.jsonl`，
    而读者那份可能已经填了 20 条人判的 expected——判分器不该覆盖它。
    沙箱里只放脚本和夹具日志，跑完就删。
    """

    def __init__(self, target: Path):
        self.target = target
        self.script = target / "evals" / "mine_failures.py"
        self._sbx = tempfile.TemporaryDirectory(prefix="p3-13-sbx-")
        root = Path(self._sbx.name)
        (root / "evals").mkdir()
        (root / "logs").mkdir()
        shutil.copy2(self.script, root / "evals" / "mine_failures.py")
        (root / "logs" / "runs.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in LOG_ROWS), encoding="utf-8",
        )
        self.root = root
        self.out_path = root / "evals" / "v2.jsonl"
        r = subprocess.run(
            [sys.executable, str(root / "evals" / "mine_failures.py")], cwd=str(root),
            capture_output=True, text=True, timeout=120,
        )
        self.rc = r.returncode
        self.stdout = r.stdout
        self.stderr = r.stderr
        self.rows: list[dict] = []
        self.parse_err: list[str] = []
        if self.out_path.exists():
            for line in self.out_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    self.parse_err.append(f"{line[:60]}… ({exc})")
                    continue
                if isinstance(row, dict):
                    self.rows.append(row)
        self.by_question = {str(r.get("question", "")): r for r in self.rows}

    def need_rows(self) -> None:
        assert self.rc == 0, (
            f"脚本退出码 {self.rc}。stderr 末几行：\n"
            + "\n".join(self.stderr.strip().splitlines()[-6:])
        )
        assert self.out_path.exists(), (
            f"脚本跑完了但没有 {self.out_path.name}——产出要落在 evals/v2.jsonl"
        )


# ---------- 能跑、能读 ----------
def c1_runs(ctx: Ctx) -> str:
    ctx.need_rows()
    return "脚本退出码 0"


def c2_parsable(ctx: Ctx) -> str:
    ctx.need_rows()
    assert not ctx.parse_err, f"输出有坏行：{ctx.parse_err[:2]}"
    assert ctx.rows, "输出文件是空的——一条都没挖出来"
    return f"{len(ctx.rows)} 行可解析"


# ---------- 挖到了什么 ----------
def c3_count(ctx: Ctx) -> str:
    ctx.need_rows()
    assert len(ctx.rows) == len(EXPECT_KINDS), (
        f"挖出 {len(ctx.rows)} 条，按失败类型去重后应有 {len(EXPECT_KINDS)} 条。\n"
        "          9 条日志里有 5 种失败类型（timeout 出现两次，只留一条）"
    )
    return f"{len(ctx.rows)} 条待填"


def c4_signals(ctx: Ctx) -> str:
    ctx.need_rows()
    qs = set(ctx.by_question)
    hit = {q for q in qs if any(w in q for w in ("notes/plan", "网页", "项目的结构", "报销"))}
    assert len(hit) >= 4, (
        f"四种失败信号里只挖到 {len(hit)} 种：{sorted(hit)}\n"
        "          预期分别由 error / retries>=2 / tool_calls>15 / user_score<0.5 命中"
    )
    return f"四种信号都挖到了（{len(hit)} 条）"


def c5_dedupe(ctx: Ctx) -> str:
    ctx.need_rows()
    timeouts = [r for r in ctx.rows if "notes/" in str(r.get("question", ""))]
    assert len(timeouts) == 1, (
        f"同类失败（timeout）留下了 {len(timeouts)} 条：{[r.get('question') for r in timeouts]}\n"
        "          不去重的话，一类失败会占掉测试集一半——通过率只反映那一类"
    )
    return "同类失败只留一条"


def c6_unknown_kind(ctx: Ctx) -> str:
    ctx.need_rows()
    hit = [r for r in ctx.rows if "config.toml" in str(r.get("question", ""))]
    assert hit, (
        "漏掉了没有 error_type 的那条（读 config.toml）。"
        "只按 error_type 分桶、丢掉「未知」的实现会把一整类失败排除在评测之外"
    )
    return "未知类型也收进来了"


def c7_no_false_positive(ctx: Ctx) -> str:
    ctx.need_rows()
    bad = [q for q in ctx.by_question if q in HEALTHY]
    assert not bad, (
        f"正常的 run 被挖出来了：{bad}\n"
        "          误报比漏报更伤：它把「本来是对的」写进失败集，"
        "于是你按这个集合去改，改的是不存在的 bug"
    )
    return "正常样本没被误报"


# ---------- 产出格式 ----------
def c8_expected_empty(ctx: Ctx) -> str:
    ctx.need_rows()
    filled = [(r.get("id"), r.get("expected")) for r in ctx.rows if str(r.get("expected") or "").strip()]
    assert not filled, (
        f"这些条目的 expected 不是空的：{filled[:3]}\n"
        "          expected 必须人填。让模型填等于让出题人自己批改——"
        "它会认为自己的输出是对的，通过率虚高，而面试里解释不通"
    )
    return "expected 一律留空"


def c9_ids(ctx: Ctx) -> str:
    ctx.need_rows()
    ids = [str(r.get("id")) for r in ctx.rows]
    dup = {i for i in ids if ids.count(i) > 1}
    assert not dup, f"id 重复：{sorted(dup)[:3]}"
    bad = [i for i in ids if not i.startswith("mined-")]
    assert not bad, f"id 没有 mined- 前缀：{bad[:3]}——挖来的 case 要能和 v1 手写的区分开"
    return f"{len(set(ids))} 个 id 唯一"


def c10_source(ctx: Ctx) -> str:
    ctx.need_rows()
    bad = [r.get("id") for r in ctx.rows if r.get("source") != "trace"]
    assert not bad, f"source 不是 trace：{bad[:3]}——以后补别处来的 case 时，靠这个字段分得开"
    return "source 都是 trace"


def c11_question_kept(ctx: Ctx) -> str:
    ctx.need_rows()
    origin = {r["input"] for r in LOG_ROWS}
    bad = [q for q in ctx.by_question if q not in origin]
    assert not bad, f"question 不是原文照搬：{bad[:2]}——改写会让判分变模糊"
    return "问题原文照搬"


def c12_actual_kept(ctx: Ctx) -> str:
    ctx.need_rows()
    want = {r["input"]: r.get("final_answer", "") for r in LOG_ROWS}
    bad = []
    for q, row in ctx.by_question.items():
        if q in want and str(row.get("actual", "")) != str(want[q]):
            bad.append(q)
    assert not bad, (
        f"actual 和日志里的 final_answer 不一致：{bad[:2]}——"
        "挖出来的 case 要留住「当时它答了什么」，那是你判 expected 的唯一依据"
    )
    return "actual 保留了当时的回答"


def c13_reports_count(ctx: Ctx) -> str:
    ctx.need_rows()
    n = len(ctx.rows)
    assert str(n) in ctx.stdout, (
        f"脚本没有打印「{n} 条待填 expected」这类汇总（实际输出：{ctx.stdout.strip()[:80]!r}）。\n"
        "          挖完就报个数：下一步是人工填 expected，没有提示就容易被忘掉"
    )
    return f"打印了 {n} 条"


CHECKS = [
    ("脚本能跑通", c1_runs),
    ("输出每行可解析", c2_parsable),
    ("按失败类型去重后 5 条", c3_count),
    ("四种失败信号都命中", c4_signals),
    ("同类失败只留一条", c5_dedupe),
    ("未知类型也收", c6_unknown_kind),
    ("正常样本没被误报", c7_no_false_positive),
    ("expected 一律留空", c8_expected_empty),
    ("id 唯一且有 mined- 前缀", c9_ids),
    ("source 是 trace", c10_source),
    ("问题原文照搬", c11_question_kept),
    ("actual 保留当时回答", c12_actual_kept),
    ("跑完报出条数", c13_reports_count),
]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="判 P3-13 的失败挖矿脚本")
    ap.add_argument("--target", default=".", help="项目根目录（含 evals/ 与 logs/）")
    args, rest = ap.parse_known_args()

    target = Path(args.target).expanduser().resolve()
    if not (target / "evals" / "mine_failures.py").is_file():
        return exit_missing(
            f"× 在 {target} 下没找到 evals/mine_failures.py",
            "  用 --target 指到项目根目录",
            "  CONTRACT §1 要求挖矿脚本在这里，读 logs/runs.jsonl 写 evals/v2.jsonl",
        )
    try:
        ctx = Ctx(target)
    except subprocess.TimeoutExpired:
        return exit_missing("× 脚本跑了 120 秒还没结束——检查是不是死循环了")
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return exit_missing(f"× 跑脚本失败：{type(exc).__name__}: {exc}")

    return run_all(
        "P3-13 判分 · 失败挖矿",
        CHECKS,
        ctx,
        argv=rest,
        subtitle=f"目标 {target}（在临时沙箱里跑，日志是夹具给的 9 条）",
        footer=(
            "注意：这里判「挖矿逻辑」，判不了「expected 填得对不对」——那必须人判。\n"
            "      卡里那句话就是重点：哪怕只有 10 条，也要你亲自判一次。"
        ),
    )


if __name__ == "__main__":
    sys.exit(main())
