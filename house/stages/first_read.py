"""Stage 2: first read. Wonder reads the whole source once and writes the house's reading."""

from house import context
from house.client import WONDER, Call, load_schema


def run(ctx) -> None:
    inp = context.join(context.work_card(ctx.work), context.source_text(ctx.work))
    res = ctx.call("first-read", Call("first-read", WONDER, "medium", inp, load_schema("first-read"),
                                      f"{ctx.work_id}:source", expected_output_tokens=6000))
    eid = ctx.emit("first-read", "reading.written", {"version": ctx.version("reading") + 1, "crux": res.data["crux"]},
                   call_id=res.call_id)
    ctx.save("reading", res.data, eid)
