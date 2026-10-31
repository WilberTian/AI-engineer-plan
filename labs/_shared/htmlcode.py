"""从手册 HTML 里现抽代码块。

为什么抽而不存副本：仓库里存第二份参考实现，改一边忘一边，不报错，
只会悄悄变成两套说法。手册是唯一来源，判分从它现读——
对不上就是真问题，正好该被发现。

用法：
    from htmlcode import block, blocks, sha
    block("stage-p1.html", "p1-9")        # 第 1 个代码块原文
    block("stage-p1.html", "p1-9", 0)     # 同上
    blocks("stage-p1.html", "p1-9")       # 全部
"""
from __future__ import annotations

import hashlib
import html as _html
import re
from pathlib import Path

# labs/_shared/htmlcode.py → 上两级就是站点根目录
REPO = Path(__file__).resolve().parent.parent.parent


def _read(page: str) -> str:
    p = Path(page)
    if not p.is_absolute():
        p = REPO / page
    return p.read_text(encoding="utf-8")


def blocks(page: str, card_id: str) -> list[str]:
    """取某张卡里全部代码块的**纯文本原文**（已解 HTML 转义、已去标注 span）。"""
    src = _read(page)
    m = re.search(
        r'<details class="task"[^>]*id="%s"(.*?)</details>' % re.escape(card_id),
        src, re.S,
    )
    if not m:
        raise LookupError(f"{page} 里找不到卡片 {card_id}")
    out = []
    for raw in re.findall(r"<pre><code[^>]*>(.*?)</code></pre>", m.group(1), re.S):
        out.append(_html.unescape(re.sub(r"<[^>]+>", "", raw)))
    if not out:
        raise LookupError(f"{page} 的 {card_id} 里没有代码块")
    return out


def block(page: str, card_id: str, idx: int = 0) -> str:
    return blocks(page, card_id)[idx]


def sha(text: str) -> str:
    """代码块指纹。行号会随内容漂，指纹不会。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
