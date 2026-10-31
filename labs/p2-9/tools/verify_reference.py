"""证明「参考实现能过判分」。两个代码块合并成一个 cite.py（手册分两段讲同一模块）。

    python3 labs/p2-9/tools/verify_reference.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from refkit import verify_reference  # noqa: E402

# 参考实现的分句只按「。」和换行，且过滤掉 15 字以下的句子：
# 短结论句被整句跳过，英文整段只算一句。两条都是漏检，见 NOTES §2。
KNOWN_RED = ["短句也检查", "英文句子也被切分"]


def build(tmp: Path, code: str) -> None:
    p = tmp / "agentlab" / "rag"
    p.mkdir(parents=True)
    (tmp / "agentlab" / "__init__.py").write_text("", encoding="utf-8")
    (p / "__init__.py").write_text("", encoding="utf-8")
    (p / "cite.py").write_text(code, encoding="utf-8")


def main() -> int:
    return verify_reference(
        page="stage-p2.html", card="p2-9", lab=LAB, build=build,
        combine=[1, 0], expect_red=KNOWN_RED,
    )


if __name__ == "__main__":
    sys.exit(main())
