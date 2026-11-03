"""Stage 16: release, code only. The views (Casual / Curious / Student) share one English and
differ in their notes. Proof/QC is code: every paragraph present, every note anchored. Labels say what
happened to each paragraph, in words; "reviewed" is kept for a second, different person, as Wikisource keeps
it (docs/REFERENCES.md). The release carries the Aozora colophon, as Aozora's terms ask."""

import json

from house import queries
from house.db import data_dir, dumps
from house.stages.common import latest_units

VIEWS = ("casual", "curious", "student")


def label(ctx, pid: str) -> str:
    checked = ctx.conn.execute("SELECT 1 FROM event WHERE run_id=? AND type='chapter.read' AND payload LIKE ?",
                               (ctx.run_id, f'%"{pid}"%')).fetchone()
    return "house-checked" if checked else "draft"


def run(ctx) -> dict:
    # A group the drafter joined is aligned group to group: its English sits on the first paragraph,
    # and the others say which paragraph carries it (docs/STAGES.md, "Groups").
    english, grouped = {}, {}
    for unit, en in latest_units(ctx).items():
        english[unit[0]] = en
        for pid in unit[1:]:
            english[pid], grouped[pid] = "", unit[0]
    paras = ctx.work.translatable()
    problems = [f"{p.id} has no English" for p in paras if p.id not in english]
    notes = [dict(r) for r in ctx.conn.execute("SELECT * FROM note WHERE run_id=? AND status != 'killed'", (ctx.run_id,))]
    ids = {p.id for p in paras}
    problems += [f"note {n['id']} anchored to missing {n['anchor']}" for n in notes if n["anchor"].split("-")[0] not in ids]

    views = {}
    for view in VIEWS:
        views[view] = [{
            "id": p.id, "ja": p.text, "en": english.get(p.id, ""),
            "grouped_with": grouped.get(p.id), "scene_break_before": p.scene_break_before, "label": label(ctx, p.id),
            "open_queries": len(queries.open_queries(ctx, p.id)),
            "notes": [{"anchor": n["anchor"], "span": n["span"], "body": n["body"], "sources": json.loads(n["sources"]),
                       "status": n["status"]} for n in notes if n["anchor"].split("-")[0] == p.id
                      and view in json.loads(n["editions"])],
        } for p in paras]

    for p in paras:
        ctx.conn.execute("INSERT INTO status (work_id, segment_id, label, who) VALUES (?,?,?,?) "
                         "ON CONFLICT(work_id, segment_id) DO UPDATE SET label=excluded.label, who=excluded.who",
                         (ctx.work_id, p.id, label(ctx, p.id), "the house"))
    editor = ctx.options.get("credit") or "the house"  # a run from the editors' desk carries the editor's credit
    # An edition belongs to whoever ran it: an editor's next run of a work revises their own edition, and
    # nobody's credit, however they spell it, lands in someone else's (or the house's).
    ed = ctx.conn.execute("SELECT e.id FROM edition e WHERE e.work_id=? AND e.editor=? AND NOT EXISTS ("
                          "SELECT 1 FROM release r JOIN run u ON u.id = r.run_id WHERE r.edition_id = e.id "
                          "AND json_extract(u.options, '$.editor_id') IS NOT ?)",
                          (ctx.work_id, editor, ctx.options.get("editor_id"))).fetchone()
    ed_id = ed["id"] if ed else ctx.conn.execute("INSERT INTO edition (work_id, editor) VALUES (?,?)",
                                                 (ctx.work_id, editor)).lastrowid
    if ctx.options.get("accent"):  # the colour the editor picked on the desk
        ctx.conn.execute("UPDATE edition SET accent=? WHERE id=?", (ctx.options["accent"], ed_id))
    n = ctx.conn.execute("SELECT COUNT(*) FROM release WHERE edition_id=?", (ed_id,)).fetchone()[0]
    version = f"v0.{n + 1}"
    body = {"work": ctx.work_id, "title": ctx.work.title, "author": ctx.work.author, "colophon": ctx.work.colophon,
            "views": views, "qc": problems, "reading": ctx.latest("reading"), "bible": ctx.latest("bible")}
    cur = ctx.conn.execute("INSERT INTO release (edition_id, run_id, version, changelog, credits, body) VALUES (?,?,?,?,?,?)",
                           (ed_id, ctx.run_id, version, f"House run {ctx.run_id}; not yet read by the editor.",
                            dumps({"house": "keikaku", "models": sorted({r["model"] for r in ctx.conn.execute(
                                "SELECT DISTINCT model FROM call WHERE run_id=? AND ok=1", (ctx.run_id,))})}), dumps(body)))
    ctx.conn.execute("UPDATE edition SET current_release=? WHERE id=?", (cur.lastrowid, ed_id))
    ctx.conn.commit()
    out = data_dir() / "releases" / f"{ctx.work_id}-{version}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
    ctx.emit("house", "release.made", {"version": version, "release_id": cur.lastrowid, "qc": problems,
                                       "paragraphs": len(paras), "notes": len(notes)})
    return {"version": version, "qc_problems": len(problems)}
