"""判分器自己的体检：先按 NOTES §4 修掉参考实现的两个洞，再往里塞 bug。

    uv run python labs/p1-2/tools/self_test.py

为什么要先修：手册当前版本有两条不达标（默认值不校验、字段顺序取不到 refused），
不修的话「塞 bug」这一步落在一个本来就红的基础上，证明不了任何事。
修法就是把 field_validator 换成 model_validator(mode="after")，两处 patch，不是另写一份实现。

每个 mutation 打一条不同的检查，所以漏掉哪条一眼能看出来。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from htmlcode import block                 # noqa: E402
from mutate import patch, run_mutations    # noqa: E402

RUN_CHECKS = LAB / "harness" / "run_checks.py"
CARD, IDX = "p1-2", 0

# 让参考实现达标的两个最小修正（NOTES §4）
FIXES = [
    (
        "from pydantic import BaseModel, Field, field_validator",
        "from pydantic import BaseModel, Field, model_validator",
    ),
    (
        '    @field_validator("citations")\n'
        "    @classmethod\n"
        "    def need_citation_unless_refused(cls, v: list[Citation], info):\n"
        "        # 关键业务规则：要么有引用，要么明确拒答。两者都不满足就是坏数据。\n"
        '        if not v and not info.data.get("refused", False):\n'
        '            raise ValueError("非拒答回答必须至少有一条引用")\n'
        "        return v",
        '    @model_validator(mode="after")\n'
        "    def need_citation_unless_refused(self):\n"
        "        # 关键业务规则：要么有引用，要么明确拒答。两者都不满足就是坏数据。\n"
        "        if not self.citations and not self.refused:\n"
        '            raise ValueError("非拒答回答必须至少有一条引用")\n'
        "        return self",
    ),
]

MUTATIONS = [
    (
        "confidence 去掉枚举约束",
        '    confidence: Literal["high", "medium", "low"]',
        "    confidence: str",
        "confidence 非法值被拒",
    ),
    (
        "quote 去掉长度上限",
        '    quote: str = Field(min_length=1, max_length=300, description="原文片段")',
        '    quote: str = Field(min_length=1, description="原文片段")',
        "quote 超长被拒",
    ),
    (
        "doc_id 允许 None",
        '    doc_id: str = Field(description="来源文档 ID，必须来自检索结果，不允许编造")',
        '    doc_id: str | None = Field(description="来源文档 ID，必须来自检索结果，不允许编造")',
        "doc_id=None 被拒",
    ),
    (
        "业务规则整个不生效",
        '        if not self.citations and not self.refused:\n'
        '            raise ValueError("非拒答回答必须至少有一条引用")',
        "        pass  # mutation: 规则不生效",
        "citations=[] 且 refused=False 被拒",
    ),
    (
        "refused 默认值写反",
        '    refused: bool = Field(default=False, description="是否因缺少依据而拒答")',
        '    refused: bool = Field(default=True, description="是否因缺少依据而拒答")',
        "refused 默认 False",
    ),
]


def build(tmp: Path, schema_src: str) -> None:
    pkg = tmp / "agentlab"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "schema.py").write_text(schema_src, encoding="utf-8")


def run_checks(target: Path) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, str(RUN_CHECKS), "--target", str(target)],
        capture_output=True, text=True,
    )
    return r.returncode, r.stdout + r.stderr


def main() -> int:
    return run_mutations(
        "P1-2 判分器体检：塞 bug → 判分必须红",
        baseline=patch(block("stage-p1.html", CARD, IDX), FIXES),
        mutations=MUTATIONS,
        build=build,
        run_checks=run_checks,
    )


if __name__ == "__main__":
    sys.exit(main())
