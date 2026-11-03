"""Stage 6: draft. Translation drafts page by page, in order, each page seeing the previous
pages' English. Context per docs/STORY-STATE.md §3; no referent map: the drafter works out who
speaks and acts from the text, the cast and the paragraphs either side. The orchestrator checks
every paragraph of a page is covered exactly once; what an answer leaves out is drafted again on its own.

The model and the prompt are run options (orchestrator.DEFAULTS).

Why the draft leans to English, from our experiments on 晩餐: a lost image or a varied repetition
is a few words, and the faithful reader can point the desk at it. A sentence built in Japanese
order needs a new sentence, and after this stage nobody writes whole sentences. A draft that wrote
English first came out more faithful as well as more readable than one written to be faithful first. It's also
the order translators describe (Hahn, Catching Fire, 2022), and literalness is the models' trained-in default
(Li et al. 2025), so the draft is where to push against it (docs/REFERENCES.md).
"""

from types import SimpleNamespace

from house import context, pager
from house.client import PROMPTS, Call, load_schema
from house.db import dumps
from house.stages.common import DEFAULTS, latest_english, model

ACTOR = "translation/drafter"


class CoverageError(Exception):
    pass


def voice_block(take: dict) -> str:
    return context.block("The voice for this text", f"{take['label']}: {take['line']}")


def voice_take(ctx) -> dict:
    """The voice the drafter writes in: the first the house's reading proposes, unless the run's
    options name another by its position (options['voice'], from 0: the editor's pick)."""
    takes = ctx.latest("reading")["voice_takes"]
    return takes[min(int(ctx.options.get("voice") or 0), len(takes) - 1)]


def stable_for(ctx, take: dict) -> str:
    """What every drafting call carries before its page: the reading, the voice, the bible. The source
    is added per page. The checkpoint drafts page 1 under each voice take with the same prefix, so the
    take the editor approves is the draft stage's own first page, served from the cache."""
    return context.join(context.reading(ctx.latest("reading")), voice_block(take), context.bible(ctx.latest("bible")))


def draft_prompt(ctx) -> str:
    """The drafting prompt a run uses, options['draft_prompt']: translate-draft-plain (the default, a
    fluent first draft) or translate-draft (faithful first). Every variant answers to the same schema."""
    name = ctx.options.get("draft_prompt") or DEFAULTS["draft_prompt"]
    if not name.startswith("translate-draft") or not (PROMPTS / f"{name}.md").exists():
        raise ValueError(f"no drafting prompt called {name!r}")
    return name


def repair(items: list[dict], ids: list[str]) -> tuple[list[dict], list[str]]:
    """Keep what the answer got right: paragraphs not on this page are dropped (the drafter sometimes
    translates the next paragraph it was shown), a paragraph drafted twice keeps its first draft.
    Returns the usable items and the paragraphs still missing, in page order."""
    seen, kept = set(), []
    for it in items:
        own = [i for i in it["ids"] if i in ids]
        if own and not set(own) & seen:
            kept.append({**it, "ids": own})
            seen.update(own)
    return kept, [i for i in ids if i not in seen]


def draft_page(ctx, paras, all_paras, stable, voice_ref):
    stable = context.join(stable, context.source_text(ctx.work, paras, ctx.latest("bible").get("chapter_summaries")))
    english = latest_english(ctx)
    idx = all_paras.index(paras[0])
    before = [(p, english.get(p.id)) for p in all_paras[max(0, idx - 2):idx]]
    after_i = all_paras.index(paras[-1]) + 1
    after = all_paras[after_i] if after_i < len(all_paras) else None
    passage = context.join(voice_ref, context.window(before, after), context.page(paras))
    ids = [p.id for p in paras]
    res = ctx.call(ACTOR, Call(draft_prompt(ctx), model(ctx, "draft_model"), "medium", context.join(stable, passage),
                               load_schema("translate-draft"), f"{ctx.cache_key()}:draft", expected_output_tokens=5000))
    items, missing = repair(res.data["items"], ids)
    if missing:  # what the answer left out is drafted again on its own, as a page of its own
        ctx.emit("house", "check.flagged", {"segment_id": missing[0], "check": f"the draft left out {', '.join(missing)}: drafting them again"})
        again = [p for p in paras if p.id in missing]
        more = ctx.call(ACTOR, Call(draft_prompt(ctx), model(ctx, "draft_model"), "medium",
                                    context.join(stable, context.window(before, after), context.page(again)),
                                    load_schema("translate-draft"), f"{ctx.cache_key()}:draft", expected_output_tokens=5000))
        extra, missing = repair(more.data["items"], missing)
        items += extra
        if missing:
            raise CoverageError(f"the draft left out {', '.join(missing)} twice")
    order = {i: n for n, i in enumerate(ids)}
    return SimpleNamespace(data={"items": sorted(items, key=lambda it: order[it["ids"][0]])}, call_id=res.call_id)


def store(ctx, res) -> list[int]:
    out = []
    for it in res.data["items"]:
        v = ctx.conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM revision WHERE run_id=? AND segment_ids=? AND variant='lead'",
            (ctx.run_id, dumps(it["ids"]))).fetchone()[0]
        cur = ctx.conn.execute(
            "INSERT INTO revision (run_id, work_id, segment_ids, version, english, notes) VALUES (?,?,?,?,?,?)",
            (ctx.run_id, ctx.work_id, dumps(it["ids"]), v, it["english"], dumps(it["notes"])))
        rid = cur.lastrowid
        eid = ctx.emit(ACTOR, "draft.paragraph", {"ids": it["ids"], "revision_id": rid, "variant": "lead",
                                                  "english": it["english"], "notes": it["notes"]},
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
    all_paras = ctx.work.translatable()
    pages = pager.pages(ctx.work.paragraphs)
    ctx.emit("house", "page.cut", {"pages": [[p.id for p in pg] for pg in pages]})
    stable = stable_for(ctx, voice_take(ctx))  # source added per page

    done = set(latest_english(ctx))
    voice_ref = ""
    drafted = 0
    for n, paras in enumerate(pages):
        if n == 1:  # from page 2 on, the drafter matches the voice of the house's first page
            en = latest_english(ctx)
            voice_ref = context.voice_reference([(p.id, en[p.id]) for p in pages[0] if p.id in en])
        if all(p.id in done for p in paras):
            continue
        store(ctx, draft_page(ctx, paras, all_paras, stable, voice_ref))
        drafted += 1
    return {"pages": len(pages), "drafted": drafted, "model": model(ctx, "draft_model")}
