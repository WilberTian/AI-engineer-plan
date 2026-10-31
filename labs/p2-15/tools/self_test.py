"""判分器体检：把合规规格弄坏一处，对应的检查必须变红。

    python3 labs/p2-15/tools/self_test.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from datafix import self_test  # noqa: E402

from verify_contract import fixture  # noqa: E402

KEY = "tools/search.json"


def _mut(tree, fn):
    spec = json.loads(tree[KEY])
    fn(spec)
    tree[KEY] = json.dumps(spec, ensure_ascii=False, indent=2)
    return tree


def drop_counterexample(tree):
    """删掉「何时别用」段——三段里最容易被省、也最值钱的一段。"""
    def f(spec):
        cut = spec["description"].split("何时别用")[0]
        spec["description"] = cut + "返回：若干片段。"
    return _mut(tree, f)


def shorten_description(tree):
    def f(spec):
        spec["description"] = "搜索文档库"
    return _mut(tree, f)


def required_ghost(tree):
    def f(spec):
        spec["parameters"]["required"] = ["query", "lang"]
    return _mut(tree, f)


def param_without_desc(tree):
    def f(spec):
        del spec["parameters"]["properties"]["query"]["description"]
    return _mut(tree, f)


def open_params(tree):
    def f(spec):
        spec["parameters"]["additionalProperties"] = True
    return _mut(tree, f)


def too_many_params(tree):
    def f(spec):
        props = spec["parameters"]["properties"]
        for k in ("top_k", "lang", "rerank", "timeout", "debug"):
            props[k] = {"type": "string", "description": f"{k} 参数"}
    return _mut(tree, f)


def split_by_interface(tree):
    """name 改成 search_by_title——照着后端接口切工具的典型痕迹。"""
    def f(spec):
        spec["name"] = "search_by_title"
    return _mut(tree, f)


MUTATIONS = [
    ("删掉「何时别用」段", drop_counterexample, "写了何时别用"),
    ("描述缩成「搜索文档库」", shorten_description, "描述够长"),
    ("required 指向不存在的参数", required_ghost, "required 非空且不指向不存在的参数"),
    ("某个参数删掉说明", param_without_desc, "每个参数都有说明"),
    ("additionalProperties 放开", open_params, "参数空间已收紧"),
    ("参数堆到 7 个", too_many_params, "参数不超过 6 个"),
    ("name 改成 search_by_title", split_by_interface, "name 没有按接口拆"),
]


def main() -> int:
    return self_test(lab=LAB, tree=fixture(), mutations=MUTATIONS)


if __name__ == "__main__":
    sys.exit(main())
