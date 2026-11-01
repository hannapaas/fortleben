"""Stage 6: draft. Translation drafts page by page, in order, each page seeing the previous
pages' English. Context per docs/STORY-STATE.md §3. The orchestrator checks every paragraph
of a page is covered exactly once (retry once, then a failure event).

With options['compare_referents'] = N, the first N pages are also drafted without the referent
entries (variant 'no-referents'), everything else equal, so the editor can read both
(docs/STORY-STATE.md §1, "The referent map has to earn its place").
"""

import json

from house import context, pager
from house.client import SPARK, Call, load_schema
from house.db import dumps


class CoverageError(Exception):
    pass


def voice_take(ctx) -> str:
    takes = ctx.latest("reading")["voice_takes"]
    wanted = ctx.options.get("voice")
    take = next((t for t in takes if t["label"] == wanted), takes[0])
    return context.block("The voice for this text", f"{take['label']}: {take['line']}")


def coverage(items: list[dict], ids: list[str]) -> list[str]:
    """Problems with the answer's coverage of the page: missing, doubled, or foreign ids."""
    seen = [i for it in items for i in it["ids"]]
    problems = [f"missing {i}" for i in ids if i not in seen]
    problems += [f"twice {i}" for i in set(seen) if seen.count(i) > 1]
    problems += [f"not on this page {i}" for i in set(seen) if i not in ids]
    return problems


def latest_english(ctx, variant: str = "lead") -> dict[str, str]:
    rows = ctx.conn.execute(
        "SELECT segment_ids, english FROM revision WHERE run_id=? AND variant=? ORDER BY id", (ctx.run_id, variant)).fetchall()
    out = {}
    for r in rows:
        ids = json.loads(r["segment_ids"])
        for i in ids:
            out[i] = r["english"] if len(ids) == 1 else f"[grouped with {', '.join(ids)}] {r['english']}"
    return out


def draft_page(ctx, paras, all_paras, stable, voice_ref, refmap, with_referents: bool):
    english = latest_english(ctx)
    idx = all_paras.index(paras[0])
    before = [(p, english.get(p.id)) for p in all_paras[max(0, idx - 2):idx]]
    after_i = all_paras.index(paras[-1]) + 1
    after = all_paras[after_i] if after_i < len(all_paras) else None
    passage = context.join(voice_ref, context.window(before, after), context.page(paras, refmap, with_referents))
    ids = [p.id for p in paras]
    note = ""
    for attempt in range(2):
        call = Call("translate-draft", SPARK, "medium", context.join(stable, passage, note),
                    load_schema("translate-draft"), f"{ctx.cache_key()}:draft", expected_output_tokens=5000)
        res = ctx.call("translation/drafter", call)
        problems = coverage(res.data["items"], ids)
        if not problems:
            return res
        note = context.block("A note on the previous attempt",
                             f"The previous answer for this page had: {'; '.join(problems)}. "
                             f"The page is {', '.join(ids)}; each must be covered exactly once.")
    ctx.emit("translation/drafter", "stage.failed", {"stage": "draft", "page": ids, "problems": problems})
    raise CoverageError(f"page {ids[0]}–{ids[-1]}: {problems}")


def store(ctx, res, variant: str) -> list[int]:
    out = []
    for it in res.data["items"]:
        v = ctx.conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM revision WHERE run_id=? AND segment_ids=? AND variant=?",
            (ctx.run_id, dumps(it["ids"]), variant)).fetchone()[0]
        cur = ctx.conn.execute(
            """INSERT INTO revision (run_id, work_id, segment_ids, version, english, spans, notes, alternatives, flags, variant)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (ctx.run_id, ctx.work_id, dumps(it["ids"]), v, it["english"], dumps(it["spans"]), dumps(it["notes"]),
             dumps(it["alternatives"]), dumps(it["flags"]), variant))
        rid = cur.lastrowid
        eid = ctx.emit("translation/drafter", "draft.paragraph",
                       {"ids": it["ids"], "revision_id": rid, "variant": variant, "english": it["english"],
                        "notes": it["notes"], "alternatives": it["alternatives"], "flags": it["flags"]},
                       call_id=res.call_id)
        ctx.conn.execute("UPDATE revision SET event_id=? WHERE id=?", (eid, rid))
        if variant == "lead":
            for sid in it["ids"]:
                ctx.conn.execute(
                    "INSERT INTO status (work_id, segment_id, label, who) VALUES (?,?,?,?) "
                    "ON CONFLICT(work_id, segment_id) DO UPDATE SET label=excluded.label, who=excluded.who",
                    (ctx.work_id, sid, "draft", "translation"))
        out.append(rid)
    ctx.conn.commit()
    return out


def run(ctx) -> dict:
    reading, bible = ctx.latest("reading"), ctx.latest("bible")
    refmap = (ctx.latest("referents") or {}).get("paragraphs", {})
    all_paras = ctx.work.translatable()
    ss = bible["style_sheet"]
    breaks = (ss.get("grain_breaks") or None) if ss["drafting_grain"] == "scene" else None
    pages = pager.pages(ctx.work.paragraphs, breaks=breaks)
    ctx.emit("house", "page.cut", {"pages": [[p.id for p in pg] for pg in pages]})
    stable = context.join(context.reading(reading), voice_take(ctx), context.bible(bible), context.source_text(ctx.work))

    compare = int(ctx.options.get("compare_referents") or 0)
    done = set(latest_english(ctx))
    voice_ref = ""
    drafted = 0
    for n, paras in enumerate(pages):
        if n == 1:  # the voice reference: the house's first page (the voice trial isn't run in the minimal pipeline)
            en = latest_english(ctx)
            voice_ref = context.voice_reference([(p.id, en[p.id]) for p in pages[0] if p.id in en])
        if not all(p.id in done for p in paras):
            store(ctx, draft_page(ctx, paras, all_paras, stable, voice_ref, refmap, True), "lead")
            drafted += 1
        if n < compare and not ctx.conn.execute(
                "SELECT 1 FROM revision WHERE run_id=? AND variant='no-referents' AND segment_ids LIKE ?",
                (ctx.run_id, f'%"{paras[0].id}"%')).fetchone():
            store(ctx, draft_page(ctx, paras, all_paras, stable, voice_ref, refmap, False), "no-referents")
    return {"pages": len(pages), "drafted": drafted, "compared": min(compare, len(pages))}
