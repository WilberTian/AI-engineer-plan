"""判分器体检：把组装顺序改坏，对应的检查必须变红。

    python3 labs/p3-12/tools/self_test.py

第一个 mutation 是最值钱的：把状态栏拼进 system，输出读起来完全一样，
只有缓存命中率会掉到 0。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from refkit import self_test  # noqa: E402

from verify_reference import build  # noqa: E402

RET = '''    return [
        {"role": "system", "content": system},
        *history,
        {"role": "user", "content": f"{state_bar}\\n\\n{user_text}"},
    ]'''

MUTATIONS = [
    (
        "状态栏拼进 system（前缀每轮都变）",
        '        {"role": "system", "content": system},',
        '        {"role": "system", "content": system + state_bar},',
        "状态栏不在 system 里",
    ),
    (
        "历史倒序",
        "        *history,",
        "        *reversed(history),",
        "历史原序保留",
    ),
    (
        "本轮提问插到历史之前",
        '''        *history,
        {"role": "user", "content": f"{state_bar}\\n\\n{user_text}"},''',
        '''        {"role": "user", "content": f"{state_bar}\\n\\n{user_text}"},
        *history,''',
        "本轮提问在最后",
    ),
    (
        "状态栏没进本轮",
        '        {"role": "user", "content": f"{state_bar}\\n\\n{user_text}"},',
        '        {"role": "user", "content": user_text},',
        "状态栏在本轮开头",
    ),
    (
        "total=0 时除零",
        '    total = getattr(usage, "prompt_tokens", 0) or 1',
        '    total = getattr(usage, "prompt_tokens", 0)',
        "total=0 不除零",
    ),
    (
        "命中数恒为 0（缓存读数写死）",
        '    hit = getattr(details, "cached_tokens", 0) if details else 0',
        "    hit = 0",
        "命中率 50/200=0.25",
    ),
    (
        "直接改传进来的 history",
        '''    return [
        {"role": "system", "content": system},''',
        '''    history.append({"role": "user", "content": "污染"})
    return [
        {"role": "system", "content": system},''',
        "入参历史未被修改",
    ),
    (
        "状态栏删掉「待办」槽位",
        "待办：{todo}",
        "下一步：{todo}",
        "状态栏模板合理",
    ),
]


def main() -> int:
    return self_test(
        page="stage-p3.html", card="p3-12", lab=LAB, build=build, mutations=MUTATIONS, combine=[0, 1],
    )


if __name__ == "__main__":
    sys.exit(main())
