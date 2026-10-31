"""证明「参考实现能过判分」。代码从 stage-p3.html 现抽。

    python3 labs/p3-5/tools/verify_reference.py

夹具另外铺 `data/corpus/*.md` 三个文件——`build_system` 里的文件数是数目录得来的，
不铺文件这条判据就测不出「写死 vs 真数」。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from refkit import verify_reference  # noqa: E402


def build(tmp: Path, code: str) -> None:
    pkg = tmp / "agentlab"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "prompt.py").write_text(code, encoding="utf-8")
    corpus = tmp / "data" / "corpus"
    corpus.mkdir(parents=True)
    for i in range(1, 4):
        (corpus / f"note-{i}.md").write_text(f"# 笔记 {i}\n\n内容\n", encoding="utf-8")


def main() -> int:
    return verify_reference(page="stage-p3.html", card="p3-5", lab=LAB, build=build)


if __name__ == "__main__":
    sys.exit(main())
