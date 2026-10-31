"""判分器自己的体检：往参考实现里塞已知 bug，看判分能不能抓住。

    python3 labs/p1-10/tools/self_test.py

为什么需要这个：一个「永远通过」的判分器等于没有判分器。
这份脚本是判分器的反例集——每个 mutation 对应一个真实踩过的坑，
如果某个 bug 塞进去判分还是全绿，说明那条断言是摆设。

这也是手册 P1-12 的原则：eval 里必须有「应该失败」的 case。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
sys.path.insert(0, str(HERE))
from htmlcode import block                 # noqa: E402
from mutate import run_mutations           # noqa: E402
from verify_reference import LLM_STUB, SOURCES  # noqa: E402

RUN_CHECKS = LAB / "harness" / "run_checks.py"

# (名字, 原文, 改坏成什么, 期望报出来的那条检查名)
MUTATIONS = [
    (
        "漏掉 assistant 消息回填",
        "        messages.append(msg.model_dump(exclude_none=True))",
        "        pass  # mutation: 不回填",
        "assistant 消息回填到下一轮",
    ),
    (
        "不截断长结果",
        '            content = result.content\n'
        '            if len(content) > max_result_chars:\n'
        '                content = content[:max_result_chars] + f"\\n...[已截断，原长 {len(content)} 字符]"',
        '            content = result.content  # mutation: 不截断',
        "超长结果被截断",
    ),
    (
        "预算耗尽时跳过 tool 消息",
        '            if tool_budget <= 0:\n'
        '                messages.append({\n'
        '                    "role": "tool",\n'
        '                    "tool_call_id": tc.id,\n'
        '                    "content": "工具调用次数已用完，请直接给出最终答案。",\n'
        '                })\n'
        '                continue',
        "            if tool_budget <= 0:\n                continue  # mutation: 不回 tool 消息",
        "步数用尽时 id 仍全对应",
    ),
    (
        "删掉「模型给结论」的出口",
        "        if not msg.tool_calls:",
        "        if False:  # mutation: 永不收敛",
        "正常收敛",
    ),
    (
        "坏 JSON 直接抛出去",
        '                result = ToolResult(ok=False, content=f"参数不是合法 JSON：{exc}")',
        "                raise  # mutation: 不兜底",
        "参数不是合法 JSON",
    ),
]


def build(tmp: Path, loop_src: str) -> None:
    pkg = tmp / "agentlab"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "llm.py").write_text(LLM_STUB, encoding="utf-8")
    (pkg / "tools.py").write_text(block("stage-p1.html", *SOURCES["tools.py"]), encoding="utf-8")
    (pkg / "loop.py").write_text(loop_src, encoding="utf-8")


def run_checks(target: Path) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, str(RUN_CHECKS), "--target", str(target)],
        capture_output=True, text=True,
    )
    return r.returncode, r.stdout + r.stderr


def main() -> int:
    return run_mutations(
        "P1-10 判分器体检：塞 bug → 判分必须红",
        baseline=block("stage-p1.html", *SOURCES["loop.py"]),
        mutations=MUTATIONS,
        build=build,
        run_checks=run_checks,
    )


if __name__ == "__main__":
    sys.exit(main())
