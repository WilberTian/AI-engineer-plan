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
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from verify_reference import LLM_STUB, REPO, SOURCES, block  # noqa: E402

RUN_CHECKS = HERE.parent / "harness" / "run_checks.py"

# (名字, 原文, 改坏成什么, 期望报出来的那条检查名)
MUTATIONS: list[tuple[str, str, str, str]] = [
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


def run_checks(target: Path) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, str(RUN_CHECKS), "--target", str(target)],
        capture_output=True, text=True,
    )
    return r.returncode, r.stdout + r.stderr


def main() -> int:
    stage = REPO / "stage-p1.html"
    tools_code = block(stage, *SOURCES["tools.py"])
    loop_code = block(stage, *SOURCES["loop.py"])

    print("=" * 74)
    print("判分器体检：塞 bug → 判分必须红")
    print("=" * 74)

    npass = nfail = 0
    for name, old, new, expect in MUTATIONS:
        if old not in loop_code:
            nfail += 1
            print(f"  FAIL  {name}")
            print("        原文没找到，mutation 失效（手册代码可能已改）")
            continue

        with tempfile.TemporaryDirectory(prefix="p1-10-mut-") as tmp:
            pkg = Path(tmp) / "agentlab"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("", encoding="utf-8")
            (pkg / "llm.py").write_text(LLM_STUB, encoding="utf-8")
            (pkg / "tools.py").write_text(tools_code, encoding="utf-8")
            (pkg / "loop.py").write_text(loop_code.replace(old, new, 1), encoding="utf-8")
            rc, out = run_checks(Path(tmp))

        caught = rc != 0 and any(
            (("FAIL" in line) or ("ERR " in line)) and expect in line
            for line in out.splitlines()
        )
        if caught:
            npass += 1
            print(f"  PASS  {name}")
            print(f"        被「{expect}」抓住")
        else:
            nfail += 1
            print(f"  FAIL  {name}")
            print(f"        期望「{expect}」报错，但 exit={rc} 且那条检查没红")
            for line in out.splitlines():
                if "PASS" in line or "FAIL" in line or "ERR" in line:
                    print(f"        | {line.strip()}")

    print("-" * 74)
    print(f"合计 {npass + nfail} 个 mutation：判分抓住 {npass} / 漏掉 {nfail}")
    if nfail:
        print("漏掉的那个断言是摆设，要改。")
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
