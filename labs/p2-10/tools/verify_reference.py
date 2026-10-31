"""证明「参考实现能过判分」。代码从 stage-p2.html 现抽。

    python3 labs/p2-10/tools/verify_reference.py

手册那段标了「节选」：`llm` / `SYSTEM_WITH_REFUSE_RULE` / `USER_TMPL` / `ctx`
都由文件外部提供。夹具把这四个名字补在文件末尾（不是改原文），
于是判分能覆盖到真正的函数体。

参考实现有一条不达标：模型返回空串时它返回 ("", "answered")。见 NOTES §2。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from refkit import verify_reference  # noqa: E402

KNOWN_RED = ["模型返回空串不算答好"]

# 手册里的函数用到四个外部名字，这里补齐。calls 记录调用次数，供「不调模型」那几条用
SHIM = '''

# ---- 判分夹具：下面四个名字在手册里由文件外部提供 ----
class _FakeLLM:
    def __init__(self) -> None:
        self.reply = "这是答案"
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        return self.reply


llm = _FakeLLM()
SYSTEM_WITH_REFUSE_RULE = "只依据给定资料回答；资料里没有就回答「资料中没有相关信息」。"
USER_TMPL = "资料：{context}\\n问题：{question}"
ctx = ""
'''


def build(tmp: Path, code: str) -> None:
    pkg = tmp / "agentlab"
    (pkg / "rag").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "rag" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "rag" / "answer.py").write_text(code + SHIM, encoding="utf-8")


def main() -> int:
    return verify_reference(
        page="stage-p2.html", card="p2-10", lab=LAB, build=build, expect_red=KNOWN_RED,
    )


if __name__ == "__main__":
    sys.exit(main())
