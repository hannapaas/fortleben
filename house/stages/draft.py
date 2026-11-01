"""Stage 6: draft. Translation drafts page by page, in order, each page seeing the previous
pages' English. Context per docs/STORY-STATE.md §3; no referent map: the drafter works out who
speaks and acts from the text, the cast and the paragraphs either side. The orchestrator checks
every paragraph of a page is covered exactly once (retry once, then a failure event).

The model is a run option, options['draft_model'] = 'spark' (default) or 'wonder'.
"""

from house import context, pager
from house.client import Call, load_schema
from house.db import dumps
from house.stages.common import latest_english, model

ACTOR = "translation/drafter"


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


def draft_page(ctx, paras, all_paras, stable, voice_ref):
    stable = context.join(stable, context.source_text(ctx.work, paras, ctx.latest("bible").get("chapter_summaries")))
    english = latest_english(ctx)
    idx = all_paras.index(paras[0])
    before = [(p, english.get(p.id)) for p in all_paras[max(0, idx - 2):idx]]
    after_i = all_paras.index(paras[-1]) + 1
    after = all_paras[after_i] if after_i < len(all_paras) else None
    passage = context.join(voice_ref, context.window(before, after), context.page(paras))
    ids = [p.id for p in paras]
    note = ""
    for attempt in range(2):
        call = Call("translate-draft", model(ctx, "draft_model"), "medium", context.join(stable, passage, note),
                    load_schema("translate-draft"), f"{ctx.cache_key()}:draft", expected_output_tokens=5000)
        res = ctx.call(ACTOR, call)
        problems = coverage(res.data["items"], ids)
        if not problems:
            return res
        note = context.block("A note on the previous attempt",
                             f"The previous answer for this page had: {'; '.join(problems)}. "
                             f"The page is {', '.join(ids)}; each must be covered exactly once.")
    ctx.emit(ACTOR, "stage.failed", {"stage": "draft", "page": ids, "problems": problems})
    raise CoverageError(f"page {ids[0]}–{ids[-1]}: {problems}")


def store(ctx, res) -> list[int]:
    out = []
    for it in res.data["items"]:
        v = ctx.conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM revision WHERE run_id=? AND segment_ids=? AND variant='lead'",
            (ctx.run_id, dumps(it["ids"]))).fetchone()[0]
        cur = ctx.conn.execute(
            "INSERT INTO revision (run_id, work_id, segment_ids, version, english, notes, flags) VALUES (?,?,?,?,?,?,?)",
            (ctx.run_id, ctx.work_id, dumps(it["ids"]), v, it["english"], dumps(it["notes"]), dumps(it["flags"])))
        rid = cur.lastrowid
        eid = ctx.emit(ACTOR, "draft.paragraph", {"ids": it["ids"], "revision_id": rid, "variant": "lead",
                                                  "english": it["english"], "notes": it["notes"], "flags": it["flags"]},
                       call_id=res.call_id)
        ctx.conn.execute("UPDATE revision SET event_id=? WHERE id=?", (eid, rid))
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
    all_paras = ctx.work.translatable()
    ss = bible["style_sheet"]
    breaks = (ss.get("grain_breaks") or None) if ss["drafting_grain"] == "scene" else None
    pages = pager.pages(ctx.work.paragraphs, breaks=breaks)
    ctx.emit("house", "page.cut", {"pages": [[p.id for p in pg] for pg in pages]})
    stable = context.join(context.reading(reading), voice_take(ctx), context.bible(bible))  # the source is added per page

    done = set(latest_english(ctx))
    voice_ref = ""
    drafted = 0
    for n, paras in enumerate(pages):
        if n == 1:  # the voice reference: the house's first page (the voice trial isn't built yet)
            en = latest_english(ctx)
            voice_ref = context.voice_reference([(p.id, en[p.id]) for p in pages[0] if p.id in en])
        if not all(p.id in done for p in paras):
            store(ctx, draft_page(ctx, paras, all_paras, stable, voice_ref))
            drafted += 1
    return {"pages": len(pages), "drafted": drafted, "model": model(ctx, "draft_model")}
