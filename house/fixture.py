"""Export a recorded run to fixtures/<work>/: every model response (so FakeClient can replay the
run with no key) and the run's record as JSON (so the site and House lanes can build on it).
download() gives an editor the same record and the finished editions, readable, as one zip.

fixtures/<work>/run.json holds the work, its paragraphs, the latest reading, crux check, bible and
parts, every revision, query, fork and note, the full event log, and the spend ledger
(model, effort, tokens, cost, prompt and input hashes) for every call. Nothing is edited by hand.
"""

import io
import json
import shutil
import zipfile
from collections import Counter
from pathlib import Path

from house.client import FIXTURES, cache_dir

TABLES = {
    "segment": "SELECT * FROM segment WHERE work_id=:work ORDER BY seq",
    "bible": "SELECT * FROM bible b WHERE work_id=:work AND version=(SELECT MAX(version) FROM bible WHERE work_id=b.work_id AND kind=b.kind) ORDER BY kind",
    "revision": "SELECT * FROM revision WHERE run_id=:run ORDER BY id",
    "query": "SELECT * FROM query WHERE run_id=:run ORDER BY id",
    "fork": "SELECT * FROM fork WHERE run_id=:run ORDER BY id",
    "note": "SELECT * FROM note WHERE run_id=:run ORDER BY id",
    "status": "SELECT * FROM status WHERE work_id=:work ORDER BY segment_id",
    "event": "SELECT * FROM event WHERE run_id=:run ORDER BY seq",
    "call": "SELECT * FROM call WHERE run_id=:run AND ok=1 ORDER BY id",
}
JSON_COLUMNS = {
    "segment": {"tokens", "sentences"}, "bible": {"body"}, "revision": {"segment_ids", "spans", "notes", "alternatives", "flags"},
    "query": {"evidence", "answer"}, "fork": {"options"}, "note": {"editions", "sources"}, "event": {"payload"},
    "work": {"rights"}, "run": {"options"},
}


def rows(conn, table: str, sql: str, args: dict) -> list[dict]:
    out = []
    for r in conn.execute(sql, args):
        d = dict(r)
        for k in JSON_COLUMNS.get(table, set()) & d.keys():
            if isinstance(d[k], str):
                d[k] = json.loads(d[k])
        out.append(d)
    return out


def run_record(conn, work_id: str, run_id: int) -> dict:
    """A run's full record: what export writes to run.json, and download puts in the zip."""
    args = {"work": work_id, "run": run_id}
    record = {"work": rows(conn, "work", "SELECT * FROM work WHERE id=:work", args)[0],
              "run": rows(conn, "run", "SELECT * FROM run WHERE id=:run", args)[0]}
    record.update({name: rows(conn, name, sql, args) for name, sql in TABLES.items()})
    release = conn.execute("SELECT body FROM release WHERE run_id=? ORDER BY id DESC LIMIT 1", (run_id,)).fetchone()
    if release:
        record["release"] = json.loads(release["body"])
    record["totals"] = {
        "calls": len(record["call"]),
        "live_cost_usd": round(sum(c["list_cost_usd"] for c in record["call"]), 4),
        "by_prompt": {},
    }
    for c in record["call"]:
        b = record["totals"]["by_prompt"].setdefault(c["prompt"], {"calls": 0, "usd": 0.0})
        b["calls"] += 1
        b["usd"] = round(b["usd"] + c["list_cost_usd"], 4)
    return record


def export(conn, work_id: str, run_id: int) -> Path:
    dest = FIXTURES / work_id
    responses = dest / "responses"
    responses.mkdir(parents=True, exist_ok=True)
    rec = run_record(conn, work_id, run_id)
    for c in rec["call"]:
        src = cache_dir() / f"{c['response_key']}.json"
        if src.exists():
            shutil.copy(src, responses / src.name)
    (dest / "run.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return dest


def edition_markdown(rec: dict, view: str) -> str:
    """One finished edition as Markdown: title, author, the English paragraph by paragraph with its
    notes as footnotes, and the colophon with the Aozora Bunko attribution."""
    rel, work = rec["release"], rec["work"]
    title = f"{work['title_en']} ({rel['title']})" if work.get("title_en") else rel["title"]
    author = f"{work['author_en']} ({rel['author']})" if work.get("author_en") else rel["author"]
    paras, notes = [], []
    for p in rel["views"][view]:  # .get: releases made by earlier pipelines lack some keys
        if p.get("grouped_with") and paras:  # its English sits on the paragraph it's grouped with
            paras[-1]["notes"] += p.get("notes") or []
            continue
        paras.append({"en": p.get("en") or "*(No English for this paragraph.)*", "notes": list(p.get("notes") or []),
                      "break": p.get("scene_break_before"), "label": p.get("label") or "draft"})
    body = []
    for p in paras:
        en = p["en"]
        for n in p["notes"]:
            notes.append(n)
            mark = f"[^{len(notes)}]"
            span = n.get("span") or ""
            en = en.replace(span, span + mark, 1) if span and span in en else en + mark
        if p["break"]:
            body.append("* * *")
        body.append(en)
    labels = Counter(p["label"] for p in paras)
    models = sorted({c["model"] for c in rec["call"]})
    head = [f"# {title}", author,
            f"*{view.capitalize()} edition.* The English is machine-drafted by the keikaku house with Meta models "
            f"({', '.join(models) or 'none recorded'}), run {rec['run']['id']}. Paragraphs: "
            + ", ".join(f"{n} {label}" for label, n in sorted(labels.items())) + ". The notes are the house's, not the author's."]
    foot = []
    for i, n in enumerate(notes, 1):
        extra = "" if n.get("status") != "unverified" else " (Unverified.)"
        sources = [s for s in n.get("sources") or [] if s != "unsourced"]
        foot.append(f"[^{i}]: {n['body']}{extra}" + (f" Sources: {'; '.join(sources)}." if sources else ""))
    card = f", {work['card_url']}" if work.get("card_url") else ""
    colophon = ["## Colophon",
                f"Japanese text: 『{rel['title']}』 {rel['author']}, from Aozora Bunko (青空文庫){card}. "
                "Aozora Bunko has not endorsed this edition.",
                "  \n".join(line for line in (rel.get("colophon") or "").splitlines() if line.strip())]
    notes_part = ["## Notes", "\n".join(foot)] if foot else []
    return "\n\n".join(head + ["---"] + body + ["---"] + notes_part + colophon) + "\n"


def download(conn, run_id: int) -> bytes:
    """A run as a zip, for the editor's own copy: run.json (the full record, as export writes it)
    and one Markdown file per finished edition. A run that hasn't released yet has the record only."""
    work_id = conn.execute("SELECT work_id FROM run WHERE id=?", (run_id,)).fetchone()["work_id"]
    return bundle(run_record(conn, work_id, run_id))


def bundle(rec: dict) -> bytes:
    work_id, run_id = rec["work"]["id"], rec["run"]["id"]
    folder = f"{work_id}-run{run_id}"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{folder}/run.json", json.dumps(rec, ensure_ascii=False, indent=1))
        for view in (rec.get("release") or {}).get("views", {}):
            z.writestr(f"{folder}/{work_id}-{view}.md", edition_markdown(rec, view))
    return buf.getvalue()
