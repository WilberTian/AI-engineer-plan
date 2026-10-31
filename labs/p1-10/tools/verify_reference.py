"""证明「参考实现能过判分」——代码从手册 HTML 里现抽，不在仓库里存第二份。

    python3 labs/p1-10/tools/verify_reference.py

为什么要抽而不是直接复制一份 loop.py 进仓库：
手册正文就是参考实现，仓库里再放一份副本，两边迟早不一致（改一边忘一边，不报错）。
抽取保证「判分跑的就是手册里那段代码」，改手册 → 这里立刻跟着变。

如果哪天这份脚本红了，说明手册里的代码和 CONTRACT 对不上了——那是真问题，不是脚本问题。
"""
from __future__ import annotations

import hashlib
import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent          # labs/p1-10/tools
REPO = HERE.parents[2]                          # 仓库根
RUN_CHECKS = HERE.parent / "harness" / "run_checks.py"

# 卡 id → 从哪张卡的第几个代码块取。顺序即依赖顺序。
SOURCES = {
    "tools.py": ("p1-9", 0),
    "loop.py": ("p1-10", 0),
}

LLM_STUB = '''"""仅供导入：loop.py 只把 LLM 当类型标注用，判分时注入的是假 provider。"""
from __future__ import annotations

from typing import Any


class LLM:
    def __init__(self, provider: Any = None) -> None:
        self.provider = provider

    def with_tools(self, messages, tools, **kw):   # pragma: no cover
        raise RuntimeError("判分不应调用真 LLM；应注入 harness/fake_llm.py")
'''


def block(stage_html: Path, card_id: str, index: int) -> str:
    src = stage_html.read_text(encoding="utf-8")
    m = re.search(r'<details class="task"[^>]*id="%s"(.*?)</details>' % re.escape(card_id), src, re.S)
    if not m:
        raise SystemExit(f"× 在 {stage_html.name} 里找不到卡片 {card_id}")
    blocks = re.findall(r"<pre><code[^>]*>(.*?)</code></pre>", m.group(1), re.S)
    if len(blocks) <= index:
        raise SystemExit(f"× 卡片 {card_id} 只有 {len(blocks)} 个代码块，取不到第 {index + 1} 个")
    return html.unescape(re.sub(r"<[^>]+>", "", blocks[index]))


def main() -> int:
    stage = REPO / "stage-p1.html"
    if not stage.is_file():
        raise SystemExit(f"× 找不到 {stage}")

    with tempfile.TemporaryDirectory(prefix="p1-10-ref-") as tmp:
        pkg = Path(tmp) / "agentlab"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "llm.py").write_text(LLM_STUB, encoding="utf-8")

        print("从手册抽取参考实现：")
        for fname, (cid, idx) in SOURCES.items():
            code = block(stage, cid, idx)
            (pkg / fname).write_text(code, encoding="utf-8")
            sha = hashlib.sha256(code.encode()).hexdigest()[:16]
            lines = code.count("\n") + 1
            print(f"  {fname:9s} ← {cid} 第 {idx + 1} 块  {lines:3d} 行  sha256 {sha}")

        print("\n用同一套判分检查它：")
        r = subprocess.run(
            [sys.executable, str(RUN_CHECKS), "--target", str(tmp)],
            text=True,
        )
        return r.returncode


if __name__ == "__main__":
    sys.exit(main())
