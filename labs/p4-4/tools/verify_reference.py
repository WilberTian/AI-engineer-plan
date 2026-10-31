"""证明「参考实现能过判分」。两个代码块合并成一个 safety.py（手册里分两段讲）。

    python3 labs/p4-4/tools/verify_reference.py

参考实现有 4 条不达标，都已核对过、写进 NOTES §2，用 expect_red 标出来而不是假装它全过。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from refkit import verify_reference  # noqa: E402

KNOWN_RED = [
    "前缀绕过 ../data-evil 被拦",
    "内网地址的拒绝理由点明「内网」",
    "内容里的开标签被转义",
    "大小写变体也转义",
    "source 属性不可注入",
]


def build(tmp: Path, code: str) -> None:
    pkg = tmp / "agentlab"
    (pkg / "resilience").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "resilience" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "resilience" / "safety.py").write_text(code, encoding="utf-8")


def main() -> int:
    return verify_reference(
        page="stage-p4.html", card="p4-4", lab=LAB, build=build,
        combine=[1, 0],              # 先 safe_path/safe_url（要 import），再 SYSTEM/wrap
        expect_red=KNOWN_RED,
    )


if __name__ == "__main__":
    sys.exit(main())
