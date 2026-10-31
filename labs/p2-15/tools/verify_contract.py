"""最小合规夹具：一份描述三段齐全的工具规格，证明判据是可满足的。

    python3 labs/p2-15/tools/verify_contract.py

夹具只保证**结构合规**。描述内容是按 CONTRACT 的要求自己写的，
不是抄手册里那份——手册那份是「好例子」的示范，照抄学不到东西。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from datafix import verify_ok  # noqa: E402

SPEC = {
    "name": "search",
    "description": (
        "在内部知识库里查资料，返回相关片段而不是整篇文档。"
        "何时用：需要具体事实、政策条款、流程步骤、准确数字或版本号时；"
        "用户问的是文档里会写明的东西时。"
        "何时别用：答案已经在上一轮对话里给过，或这是纯计算、纯推理题——直接回答，别搜；"
        "用户问的是你自己的行为（你能做什么）时也不要搜。"
        "返回：最多 8 条片段，每条带 doc_id 与 section，可以再用 read 看全文；"
        "返回空表示知识库确实没有，此时不要换成近义词反复重试超过两次。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string",
                      "description": "自然语言问句。写完整问句比堆关键词的召回率高"},
            "filters": {
                "type": "object",
                "description": "收窄检索范围的可选条件",
                "properties": {
                    "doc_type": {"type": "string",
                                 "enum": ["policy", "faq", "manual", "contract"],
                                 "description": "文档类型"},
                    "date_from": {"type": "string",
                                  "description": "只要这个日期之后的文档，ISO 格式"},
                },
                "additionalProperties": False,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}


def fixture() -> dict[str, str]:
    return {"tools/search.json": json.dumps(SPEC, ensure_ascii=False, indent=2)}


def main() -> int:
    return verify_ok(lab=LAB, tree=fixture())


if __name__ == "__main__":
    sys.exit(main())
