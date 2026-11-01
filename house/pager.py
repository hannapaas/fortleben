"""Cut a work into pages: whole paragraphs, about 650 characters, closing at scene breaks.

Deterministic; the model never decides where a page starts or ends (docs/STAGES.md,
"How pages are cut"). Scene grain closes at the Analyst's break points instead.
"""

from house.parser import Paragraph

TARGET = 650
NEAR = 0.6  # a scene break past 60% of the target closes the page early


def pages(paragraphs: list[Paragraph], target: int = TARGET, breaks: list[str] | None = None) -> list[list[Paragraph]]:
    paras = [p for p in paragraphs if p.translatable]
    if breaks:  # scene grain
        out, cur = [], []
        for p in paras:
            if p.id in breaks and cur:
                out.append(cur)
                cur = []
            cur.append(p)
        return out + ([cur] if cur else [])

    out, cur, size = [], [], 0
    for i, p in enumerate(paras):
        n = len(p.text)
        if cur and size + n > target:
            out.append(cur)
            cur, size = [], 0
        cur.append(p)
        size += n
        nxt = paras[i + 1] if i + 1 < len(paras) else None
        if nxt is not None and nxt.scene_break_before and size >= target * NEAR:
            out.append(cur)
            cur, size = [], 0
    return out + ([cur] if cur else [])
