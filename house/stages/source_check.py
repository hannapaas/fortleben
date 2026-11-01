"""Stage 7: source check. Wonder reads each page's English against the Japanese and raises
queries per paragraph, or none. Code checks run first (omission guard, ledger checker) and
their flags go to the critic as things to look at. Never skipped by the budget."""

import json

from house import checks, context, pager, queries
from house.client import WONDER, Call, load_schema
from house.stages.draft import latest_english

ACTOR = "source-check"


def terms(ctx) -> dict:
    return {r["id"]: dict(r) for r in ctx.conn.execute("SELECT * FROM term WHERE work_id=?", (ctx.work_id,))}


def stable(ctx) -> str:
    return context.join(context.reading(ctx.latest("reading")), context.bible(ctx.latest("bible")),
                        context.source_text(ctx.work))


def page_block(paras, english: dict, refmap: dict, flags: dict) -> str:
    parts = []
    for p in paras:
        part = context.referent_lines(p, refmap.get(p.id)) + f"\n  English: {english.get(p.id, '(missing)')}"
        if flags.get(p.id):
            part += "\n  Code checks flagged: " + "; ".join(flags[p.id])
        parts.append(part)
    return context.block("The page, Japanese with referent entries, and the house's English", "\n\n".join(parts))


def record(ctx, data: dict, paras, round_: int = 0) -> int:
    wanted = {p.id for p in paras}
    n = 0
    for para in data["paragraphs"]:
        if para["id"] not in wanted:
            continue
        for q in para["queries"][:queries.MAX_PER_PARAGRAPH]:
            queries.raise_query(ctx, para["id"], ACTOR, q, round_)
            n += 1
        if para["needs_second_draft"]:
            ctx.emit(ACTOR, "check.flagged", {"segment_id": para["id"], "check": "needs-second-draft"})
    return n


def check_page(ctx, paras, english, refmap, flags, extra: str = "", round_: int = 0) -> int:
    inp = context.join(stable(ctx), page_block(paras, english, refmap, flags), extra)
    res = ctx.call(ACTOR, Call("source-check", WONDER, "low", inp, load_schema("source-check"),
                               f"{ctx.cache_key()}:source-check", expected_output_tokens=3000))
    return record(ctx, res.data, paras, round_)


def code_flags(ctx, english: dict) -> dict[str, list[str]]:
    t = terms(ctx)
    pairs = {p.id: (p.text, checks.render(english[p.id], t)) for p in ctx.work.translatable() if p.id in english}
    flags: dict[str, list[str]] = {}
    for pid, why in checks.omissions(pairs).items():
        flags.setdefault(pid, []).append(why)
    for pid in pairs:
        for why in checks.ledger(english[pid], t) + checks.stray_scripts(english[pid]):
            flags.setdefault(pid, []).append(why)
    for pid, whys in flags.items():
        for why in whys:
            ctx.emit("source-check/code", "check.flagged", {"segment_id": pid, "check": why})
    return flags


def run(ctx) -> dict:
    english = latest_english(ctx)
    refmap = (ctx.latest("referents") or {}).get("paragraphs", {})
    flags = code_flags(ctx, english)
    raised = 0
    done = {json.loads(r["payload"])["ids"][0] for r in ctx.conn.execute(
        "SELECT payload FROM event WHERE run_id=? AND type='page.checked'", (ctx.run_id,))}
    for paras in pager.pages(ctx.work.paragraphs):
        if paras[0].id in done:
            continue
        n = check_page(ctx, paras, english, refmap, flags)
        ctx.emit(ACTOR, "page.checked", {"ids": [p.id for p in paras], "queries": n})
        raised += n
    return {"queries": raised, "code_flags": sum(len(v) for v in flags.values())}
