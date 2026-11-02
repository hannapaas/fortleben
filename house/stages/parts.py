"""Stage 1: parts. One cheap call looks at the book's shape (each paragraph's ID, length, kind and first
words) and says where each part starts; the readers, the desk and the final read then work a part at a
time. The model decides; code only checks the answer covers the book once, in order, with no part too
big for one reading (context.MAX_PART_CHARS). An answer that fails the check is flagged and the house
falls back to context.chapters' own split."""

from house import context
from house.client import SPARK, Call, load_schema


def outline(work) -> str:
    rows = []
    for p in work.translatable():
        marks = "".join(m for m, on in ((" heading", p.kind == "heading"), (" after a scene break", p.scene_break_before)) if on)
        rows.append(f"{p.id}  {len(p.text)} chars{marks}  {p.model_text.strip('　 ')[:30]}")
    return context.block(f"The book's shape: {len(rows)} paragraphs", "\n".join(rows))


def check(work, starts: list[str]) -> str | None:
    """Why a proposed split can't be used, or None if it can."""
    order = {p.id: i for i, p in enumerate(work.translatable())}
    if not starts or starts[0] not in order or order[starts[0]] != 0:
        return "the first part must start at the first paragraph"
    if any(s not in order for s in starts):
        return "a part starts at a paragraph that doesn't exist"
    if any(order[a] >= order[b] for a, b in zip(starts, starts[1:])):
        return "the parts are out of order"
    big = [p for p in context.split(work, starts) if sum(len(x.text) for x in p) > context.MAX_PART_CHARS]
    if big:
        return f"a part starting at {big[0][0].id} is too big for one reading"
    return None


def run(ctx) -> dict:
    res = ctx.call("planner", Call("parts", SPARK, "low", context.join(context.work_card(ctx.work), outline(ctx.work)),
                                   load_schema("parts"), f"{ctx.work_id}:parts", expected_output_tokens=1500))
    starts = res.data["starts"]
    problem = check(ctx.work, starts)
    if problem:
        ctx.emit("house", "check.flagged", {"check": f"the planner's parts can't be used ({problem}); using the book's own divisions"})
        return {"parts": len(context.chapters(ctx.work)), "planned": False}
    eid = ctx.emit("planner", "parts.planned", {"starts": starts, "why": res.data["why"]}, call_id=res.call_id)
    ctx.save("parts", {"starts": starts, "why": res.data["why"], "run_id": ctx.run_id}, eid)
    ctx.work.parts = starts
    return {"parts": len(starts), "planned": True}
