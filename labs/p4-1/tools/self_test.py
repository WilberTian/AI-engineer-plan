"""判分器体检：往 faults.py 里塞已知 bug，看判分能不能抓住。

    python3 labs/p4-1/tools/self_test.py

6 个 mutation 都对应真实会犯的错，不是随手改坏。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from refkit import self_test  # noqa: E402

from verify_reference import build  # noqa: E402

MUTATIONS = [
    (
        "关闭时返回副本（不再原样透传）",
        "    if not SPEC.enabled:\n        return result",
        "    if not SPEC.enabled:\n        return ToolResult(ok=result.ok, content=result.content)",
        "FAULTS 为空时原样透传",
    ),
    (
        "exception 分支被删（注入不再抛异常）",
        '        raise RuntimeError(f"注入异常：{tool_name} 内部崩溃")',
        "        pass",
        "exception 注入抛异常且带工具名",
    ),
    (
        "dirty 返回原文（等于没注入）",
        '        return ToolResult(ok=True, content=\'{"data": null, "note": "未找到", "code": 500}\')',
        "        return result",
        "dirty 注入是「合法但错」",
    ),
    (
        "dirty 标成失败（退化成超时那一类）",
        '        return ToolResult(ok=True, content=\'{"data": null, "note": "未找到", "code": 500}\')',
        '        return ToolResult(ok=False, content="脏数据")',
        "dirty 注入是「合法但错」",
    ),
    (
        "随机种子不固定（故障不可复现）",
        "_rng = random.Random(42)",
        "_rng = random.Random()",
        "同一配置两次加载的故障序列一致",
    ),
    (
        "环境变量解析不按白名单过滤键",
        '                if k.strip() in {"slow", "timeout", "dirty", "exception", "empty"}:\n                    kw[k.strip()] = float(v)',
        "                if True:\n                    kw[k.strip()] = float(v)",
        "未知键被忽略而不是让进程起不来",
    ),
    (
        "slow 不再真睡（变成了空转）",
        "        time.sleep(3)",
        "        pass",
        "slow 注入是真变慢",
    ),
]


def main() -> int:
    return self_test(
        page="stage-p4.html", card="p4-1", lab=LAB, build=build, mutations=MUTATIONS,
    )


if __name__ == "__main__":
    sys.exit(main())
