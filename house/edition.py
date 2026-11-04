"""What the site reads: a work's latest release, put together with its record for the reader.

The release body (house/stages/release.py) holds the views. Everything else a paragraph shows,
its margin, comes from the record anchored to it (docs/ARCHITECTURE.md §2, "The margin"):
the readers' notes and what the desk did with each, the drafter's notes, the revisions, the notes.
Live runs and `--replay` read the same tables; replay just loads them from fixtures/ first.
"""

import difflib
import html
import json
import re
from pathlib import Path

from house import works
from house.client import FIXTURES

VIEWS = ("casual", "curious", "student")
NUMBER = re.compile(r"[一二三四五六七八九十〇]+")
LANGUAGES = {"ja": ("Japanese", "日本語")}
LABELS = ("draft", "house-checked", "editor-approved", "human-reviewed")
# The colours an edition can wear: the site's pink, then the ones an editor can pick instead. A house
# edition takes them in turn by when its work arrived, so the first work is pink and the next differ.
ACCENTS = ("pink", "lime", "lavender", "peach")
READERS = {"reader/faithful": "faithful reader", "reader/readable": "readable reader"}
RUBY = re.compile(r"《[^》]*》|［＃[^］]*］")  # Aozora readings and editorial notes, quoted raw in a reader's evidence
DECIDED = {"taken": "Changed", "declined": "Kept", "forked": "Left to the editor", "open": "Not decided yet",
           "unaddressed": "Not decided yet", "noted": "Noted"}
# The first read labels its takes and marks its pick; on the page the voice is just the voice.
# Inside the engine the reading's companion document is "the bible", and its cast have ids (c1, c2).
# The model's own words sometimes carry both; what a person reads says "analysis" and drops the ids.
_BIBLE = re.compile(r"\b(?:(an?)(\s+))?(story\s+)?(bible)(s?)\b", re.I)
_CAST_IDS = re.compile(r"\b(cast)\s+c\d+(?:\s*(?:,|/|&|and)\s*c\d+)*\b", re.I)
_NOT_PROSE = frozenset({"handle", "id", "href"})
# Paragraph ids (p10) and ranges (p2–p9, p10-13, p4 to p6), and cast ids (c3, c1 and c2, c2's).
_PARA_RANGE = re.compile(r"\bp(\d+)\s*(?:[-–—]|to)\s*p?(\d+)\b")
_PARA = re.compile(r"\bp(\d+)\b")
_CAST_ONE = r"c\d+(?:['’]s)?"
_CAST_LIST = re.compile(rf"\b{_CAST_ONE}(?:\s*(?:,|/|&|and)\s*{_CAST_ONE})*\b")
_CAST_ID = re.compile(r"\bc(\d+)\b")


def _paragraphs(text: str) -> str:
    """'p10' → 'paragraph 10', 'p2–p9' → 'paragraphs 2 to 9'; capitalised at the start of the text."""
    def cap(m, word):
        return word.capitalize() if m.start() == 0 else word
    text = _PARA_RANGE.sub(lambda m: f"{cap(m, 'paragraphs')} {m.group(1)} to {m.group(2)}", text)
    return _PARA.sub(lambda m: f"{cap(m, 'paragraph')} {m.group(1)}", text)


def _cast(text: str, cast: dict[str, str] | None) -> str:
    """Cast ids as the people they name, where the bible's cast is known; otherwise dropped, with the
    brackets and commas they leave tidied."""
    if cast:
        text = _CAST_ID.sub(lambda m: cast.get(m.group(0), m.group(0)), text)
    if not _CAST_LIST.search(text):
        return text
    text = _CAST_LIST.sub("", text)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    text = re.sub(r"([(,;:])\s*,", r"\1", text)
    text = re.sub(r"[,;]\s*$", "", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def plain(text, cast: dict[str, str] | None = None):
    """Model text as a visitor or editor sees it: "story bible" and "bible" become "analysis" in the
    same case, "cast c2" becomes "cast", a paragraph id becomes "paragraph 10" (a range "paragraphs 2
    to 9"), and a cast id becomes the person's name from `cast` (id → handle) or is dropped. A capital
    "Bible" inside a sentence is left alone: a story may name the book. Anything that isn't a string
    comes back as it was. Never for ids or links: only for text a person reads."""
    if not isinstance(text, str) or not text:
        return text

    def analysis(m):
        article, space, story, bible, plural = m.groups()
        if bible == "Bible" and not story and not article and text[:m.start()].rstrip()[-1:] not in ("", *".!?:;\"'(«「"):
            return m.group(0)  # a capital Bible inside a sentence is the book, not the engine's document
        first = (story or bible).strip()
        word = "analyses" if plural else "analysis"
        word = word.upper() if first.isupper() and len(first) > 1 else word.capitalize() if first[0].isupper() else word
        if article:
            article = "AN" if article.isupper() and len(article) > 1 else "An" if article[0].isupper() else "an"
            return article + space + word
        return word

    text = _CAST_IDS.sub(lambda m: m.group(1), _BIBLE.sub(analysis, text))
    return _paragraphs(_cast(text, cast))


def plain_all(value, cast: dict[str, str] | None = None):
    """`plain` on every string in a dict or list of model output, leaving ids and links alone."""
    if isinstance(value, dict):
        return {k: v if k in _NOT_PROSE else plain_all(v, cast) for k, v in value.items()}
    if isinstance(value, list):
        return [plain_all(v, cast) for v in value]
    return plain(value, cast)


def cast_names(bible: dict | None) -> dict[str, str]:
    """The bible's cast ids and the names a reader knows them by: {'c1': 'Liu Dacheng'}."""
    return {c["id"]: c["handle"] for c in (bible or {}).get("cast") or [] if c.get("id") and c.get("handle")}


def paragraph_label(pid: str) -> str:
    """'p30' → 'paragraph 30', for a link's text; anything else as it was."""
    m = re.fullmatch(r"p(\d+)", pid or "")
    return f"paragraph {m.group(1)}" if m else pid


RECOMMENDED = re.compile(r"^\([a-z]\)\s*|\s*\(Recommended\.?\)", re.I)
OUTCOMES = {"taken": "taken", "declined": "declined", "forked": "sent to the editor", "open": "not answered yet"}

# fixture.py writes these tables; loading them back gives replay the same database a live run leaves.
# Calls go before events, which point at them.
TABLES = ("segment", "bible", "term", "call", "revision", "query", "fork", "note", "status", "event")


def load_fixtures(conn, root: Path = FIXTURES) -> list[str]:
    """Load every recorded run under fixtures/ into the database, once. Returns the works loaded.

    A recorded run keeps its id. If the database already has a run with that id it's skipped: silently
    when it's the same recording, with a warning when it's a different run (a live database that
    started before the fixtures were loaded), since nothing can be loaded over it."""
    loaded = []
    for path in sorted(root.glob("*/run.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        work_id = record["work"]["id"]
        run = record["run"]
        have = conn.execute("SELECT work_id, created_at FROM run WHERE id=?", (run["id"],)).fetchone()
        if have:
            if (have["work_id"], have["created_at"]) != (run["work_id"], run["created_at"]):
                print(f"warning: fixtures/{work_id}: run {run['id']} is already another run in this database; not loaded")
            continue
        _insert(conn, "work", record["work"], replace=True)
        _insert(conn, "run", record["run"])
        for table in TABLES:
            for row in record.get(table, []):
                _insert(conn, table, row, replace=table in ("segment", "term", "status", "bible"))
        if "release" in record:
            ed = conn.execute("INSERT INTO edition (work_id) VALUES (?)", (work_id,)).lastrowid
            rel = conn.execute("INSERT INTO release (edition_id, run_id, version, changelog, body, created_at) "
                               "VALUES (?,?,?,?,?,?)",
                               (ed, record["run"]["id"], "v0.1", "Recorded house run, replayed.",
                                json.dumps(record["release"], ensure_ascii=False), record["run"]["created_at"])).lastrowid
            conn.execute("UPDATE edition SET current_release=? WHERE id=?", (rel, ed))
        loaded.append(work_id)
    conn.commit()
    return loaded


def _insert(conn, table: str, row: dict, replace: bool = False) -> None:
    cols = list(row)
    vals = [json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for v in row.values()]
    verb = "INSERT OR REPLACE" if replace else "INSERT OR IGNORE"
    conn.execute(f"{verb} INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals)


def shelf(conn) -> list[dict]:
    """Every work with a current release, grouped by the language it was written in, newest first."""
    langs = {}
    # One row per work: its keikaku edition, or the first commissioned one if keikaku has none.
    for r in conn.execute("SELECT e.work_id, e.accent, w.language, r.version, r.created_at, r.body FROM edition e "
                          "JOIN release r ON r.id = e.current_release JOIN work w ON w.id = e.work_id "
                          "WHERE e.id = (SELECT e2.id FROM edition e2 WHERE e2.work_id = e.work_id AND e2.current_release "
                          "IS NOT NULL ORDER BY e2.editor != 'the house', e2.id LIMIT 1) ORDER BY r.created_at DESC"):
        body = json.loads(r["body"])
        paras = body["views"]["casual"]
        meta = _meta(conn, r["work_id"])
        # Paragraphs as the reader shows them: merged ones once, section numbers not at all
        shown = sum(1 for p in paras if not p["grouped_with"] and not NUMBER.fullmatch(p["ja"].strip("\u3000 ")))
        work = {**meta, "version": r["version"], "date": _date(r["created_at"]), "paragraphs": shown,
                "label": _overall([p["label"] for p in paras]), "editions": editions(conn, meta),
                "accent": accent(conn, r["work_id"], r["accent"])}
        name, native = LANGUAGES.get(r["language"], (r["language"], ""))
        langs.setdefault(r["language"], {"code": r["language"], "name": name, "native": native, "works": []})["works"].append(work)
    return list(langs.values())


def accent(conn, work_id: str, chosen: str | None = None) -> str:
    """An edition's colour: the editor's pick, or else its work's turn through ACCENTS."""
    if chosen in ACCENTS:
        return chosen
    order = [r[0] for r in conn.execute("SELECT DISTINCT w.id, w.rowid FROM work w JOIN edition e ON e.work_id = w.id "
                                        "WHERE e.editor = 'the house' AND e.current_release IS NOT NULL ORDER BY w.rowid")]
    return ACCENTS[order.index(work_id) % len(ACCENTS)] if work_id in order else ACCENTS[0]


def editions(conn, meta: dict, current: int | None = None) -> list[dict]:
    """Every English translation of a work we know of: keikaku's, then any commissioned by an editor
    from the desk, then people's by year. A person's is named with its year, and linked only where it is
    freely published (`link`, e.g. Project Gutenberg); one marked `shown: false` isn't mentioned at all."""
    ours = []
    for e in conn.execute("SELECT e.id, e.editor, r.created_at FROM edition e JOIN release r ON r.id = e.current_release "
                          "WHERE e.work_id=? ORDER BY e.editor != 'the house', e.id", (meta["id"],)):
        house = e["editor"] == "the house"
        ours.append({"kind": "house" if house else "commissioned", "by": "keikaku" if house else f"keikaku, commissioned by {e['editor']}",
                     "editor": None if house else e["editor"],
                     "year": (e["created_at"] or "")[:4], "here": True, "current": e["id"] == current,
                     "url": f"/read/{meta['id']}" + ("" if house else f"?edition={e['id']}")})
    people = [{"kind": "person", "by": t["by"], "year": str(t.get("year", "")), "here": False,
               "url": t.get("link"), "where": t.get("link_label")}
              for t in sorted(meta["rights"].get("existing_translations") or [], key=lambda t: t.get("year", 0))
              if t.get("shown", True)]
    return ours + people


def edition(conn, work_id: str, edition_id: int | None = None) -> dict | None:
    """The work's keikaku edition, or the one asked for; a work keikaku hasn't released opens its first."""
    rel = conn.execute("SELECT r.*, e.id AS edition_id, e.editor, e.accent FROM edition e JOIN release r ON r.id = e.current_release "
                       "WHERE e.work_id=? AND (? IS NULL OR e.id=?) ORDER BY e.editor != 'the house', e.id LIMIT 1",
                       (work_id, edition_id, edition_id)).fetchone()
    if not rel:
        return None
    body = json.loads(rel["body"])
    run_id = rel["run_id"]
    segs = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM segment WHERE work_id=?", (work_id,))}
    queries = _rows(conn, "SELECT * FROM query WHERE run_id=? ORDER BY id", run_id, ("evidence", "answer"))
    hand = hand_edits(conn, run_id)
    ours = {e["revision_id"] for e in hand}
    revisions = [r for r in _rows(conn, "SELECT * FROM revision WHERE run_id=? ORDER BY id", run_id, ("segment_ids", "notes"))
                 if r["id"] not in ours]  # the house's revisions; the editor's own are shown as theirs

    # One English text. The views' renderings of ledger terms are no longer offered: the text is the
    # plain (casual) rendering, and what a reader sees around it is a reading preset, not an edition.
    cast = cast_names(_document(conn, work_id, run_id, "bible"))
    units, by_id = [], {}
    for i, p in enumerate(body["views"]["casual"]):
        if p["grouped_with"]:
            by_id[p["grouped_with"]]["paras"].append(p["id"])
            continue
        unit = {"id": p["id"], "n": len(units) + 1, "paras": [p["id"]], "label": p["label"],
                "scene_break": p["scene_break_before"], "en": p["en"], "notes": _notes(body, i, cast)}
        # A paragraph that is only a section number (一, 二) is a heading, whatever the parser called it
        unit["number"] = bool(NUMBER.fullmatch(p["ja"].strip("\u3000 ")))
        units.append(unit)
        by_id[p["id"]] = unit

    for unit in units:
        ids = set(unit["paras"])
        unit["ja"] = [{"id": pid, "html": ruby_html(segs[pid])} for pid in unit["paras"] if pid in segs]
        unit["queries"] = [_query(q, cast) for q in queries if q["segment_id"] in ids]
        unit["decisions"] = _decisions(unit["queries"])
        revs = [r for r in revisions if ids & set(r["segment_ids"])]
        unit["drafter_notes"] = [n for r in revs[:1] for n in (r["notes"] or [])]
        unit["history"] = [{"version": r["version"], "en": r["english"],
                            "date": _date(r["created_at"])} for r in revs]
        unit["changed"] = len({h["en"] for h in unit["history"]}) > 1
        mine = [e for e in hand if e["ids"][0] == unit["id"]]
        if mine:
            unit["en"] = mine[-1]["english"]
        unit["edits"] = [{"by": e["by"], "date": _date(e["at"]), "diff": e.get("diff") or diff_html(e["before"], e["english"])}
                         for e in reversed(mine)]
        unit["en_html"] = mark_notes(unit["en"], unit["notes"])

    calls = conn.execute("SELECT COUNT(*), COALESCE(SUM(list_cost_usd), 0) FROM call WHERE run_id=?", (run_id,)).fetchone()
    labels = [u["label"] for u in units]
    meta = _meta(conn, work_id)
    return {
        **meta, "id": rel["edition_id"], "work_id": work_id, "version": rel["version"], "date": _date(rel["created_at"]), "units": units,
        "editions": editions(conn, meta, rel["edition_id"]),
        "commissioned_by": None if rel["editor"] == "the house" else rel["editor"],
        "accent": accent(conn, work_id, rel["accent"]),
        "counts": {label: labels.count(label) for label in LABELS},
        "edited": sum(1 for u in units if u["edits"]),
        "file_edits": file_edits(conn, run_id),
        "label": _overall(labels), "colophon": body.get("colophon") or meta.get("colophon"),
        "calls": calls[0], "cost": calls[1],
        "queries": {"total": len(queries), "taken": sum(q["status"] == "taken" for q in queries),
                    "declined": sum(q["status"] == "declined" for q in queries),
                    "forked": sum(q["status"] == "forked" for q in queries)},
        "models": sorted({r["model"] for r in conn.execute("SELECT DISTINCT model FROM call WHERE run_id=?", (run_id,))}),
        "analysis": analysis(conn, work_id, run_id, {pid: u["id"] for u in units for pid in u["paras"]}),
    }


# --- the editor's own edits ---------------------------------------------------------------------
# An edition's editor can change its English by hand at any time after it's published: each change is a
# revision of the run's English with a `revision.created` event (cause "editor") that keeps before, after and
# who. The page shows the latest over the release, and every change under the paragraph's *, as theirs.

EDIT_CHARS = 20_000  # far more than any paragraph
FILE_TITLES = {"reading": "The reading", "voices": "The voices", "bible": "The analysis"}


def owner(conn, edition_id: int) -> int | None:
    """The person whose run made the edition's current release, who may edit it; None for the house's own."""
    row = conn.execute("SELECT json_extract(u.options, '$.editor_id') AS who FROM edition e JOIN release r ON r.id = e.current_release "
                       "JOIN run u ON u.id = r.run_id WHERE e.id=?", (edition_id,)).fetchone()
    return row["who"] if row else None


def hand_edits(conn, run_id: int) -> list[dict]:
    """The editor's own changes to a run's English, oldest first: ids, before, english, by, when, revision id."""
    return [{**json.loads(r["payload"]), "at": r["created_at"]} for r in conn.execute(
        "SELECT e.payload, r.created_at FROM revision r JOIN event e ON e.id = r.event_id WHERE r.run_id=? "
        "AND e.type='revision.created' AND json_extract(e.payload, '$.cause')='editor' ORDER BY r.id", (run_id,))]


class NotEditable(Exception):
    """An edit the edition can't take, in plain words, with the HTTP status the site answers it with."""

    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.code = code


def edit(conn, edition_id: int, unit_id: str, english: str, person) -> bool:
    """The edition's editor changes one paragraph's English (a group's, for a group the drafter joined).
    Kept as a revision and an event in one transaction. False if it reads as it did."""
    if owner(conn, edition_id) != person["id"]:
        raise NotEditable("Only the editor of this edition can change its English.", 403)
    ed = conn.execute("SELECT e.editor, r.run_id, r.body, u.work_id FROM edition e JOIN release r ON r.id = e.current_release "
                      "JOIN run u ON u.id = r.run_id WHERE e.id=?", (edition_id,)).fetchone()
    if ed["editor"] == "the house":
        raise NotEditable("Only the editor of this edition can change its English.", 403)
    paras = json.loads(ed["body"])["views"]["casual"]
    unit = next((p for p in paras if p["id"] == unit_id and not p["grouped_with"]), None)
    if unit is None or NUMBER.fullmatch(unit["ja"].strip("\u3000 ")):  # a section number is a heading, not English to edit
        raise NotEditable("There's no such paragraph in this edition.", 404)
    english = re.sub(r"[ \t\r\n]+", " ", english or "").strip()  # one paragraph; other spaces (NBSP) are the editor's
    if not english:
        raise NotEditable("A paragraph can't be empty. Write the English, or leave it as it was.")
    if len(english) > EDIT_CHARS:
        raise NotEditable(f"Keep a paragraph to {EDIT_CHARS:,} characters.")
    ids = [unit_id] + [p["id"] for p in paras if p["grouped_with"] == unit_id]
    before = next((e["english"] for e in reversed(hand_edits(conn, ed["run_id"])) if e["ids"][0] == unit_id), unit["en"])
    if english == before:
        return False
    from house import events
    from house.db import dumps
    version = conn.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM revision WHERE run_id=? AND segment_ids=?",
                           (ed["run_id"], dumps(ids))).fetchone()[0]
    rid = conn.execute("INSERT INTO revision (run_id, work_id, segment_ids, version, english) VALUES (?,?,?,?,?)",
                       (ed["run_id"], ed["work_id"], dumps(ids), version, english)).lastrowid
    eid = events.emit(conn, ed["run_id"], "editor", "revision.created",
                      {"cause": "editor", "ids": ids, "revision_id": rid, "edition_id": edition_id, "before": before,
                       "english": english, "diff": diff_html(before, english), "by": ed["editor"],
                       "person_id": person["id"]}, commit=False)
    conn.execute("UPDATE revision SET event_id=? WHERE id=?", (eid, rid))
    conn.commit()
    return True


def file_edits(conn, run_id: int) -> list[dict]:
    """The editor's hand edits of the files the run was drafted from, for the appendix: which, who, when,
    and the lines that changed."""
    from house import steer
    return [{"title": f"Page 1, in the voice “{plain(e.get('label', ''))}”" if e["file"] == "page" else FILE_TITLES.get(e["file"], e["file"]),
             "by": e["by"], "date": _date(e["at"]), "cause": e.get("cause"),
             "lines": e.get("diff") or diff_lines(e["before"], e["after"])} for e in steer.edits(conn, run_id)]


_WORDS = re.compile(r"\s+|\w+|[^\w\s]")
DIFF_TOKENS = 1500  # past this a word diff gets slow (it's quadratic), so a longer change is shown whole, struck and replaced


def diff_html(before: str, after: str, context: int | None = None) -> str:
    """`after`, escaped, with what it took out struck through (<del>) and what it put in marked (<ins>), word by
    word. With `context`, a long unchanged stretch keeps only that many characters either side of a change."""
    a, b = _WORDS.findall(before or ""), _WORDS.findall(after or "")
    if len(a) > DIFF_TOKENS or len(b) > DIFF_TOKENS:
        return "".join(f"<{tag}>{html.escape(t)}</{tag}>" for tag, t in (("del", before), ("ins", after)) if t)
    ops = difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
    out = []
    for n, (op, i1, i2, j1, j2) in enumerate(ops):
        if op == "equal":
            same = "".join(a[i1:i2])
            if context and len(same) > 2 * context + 20:
                head = same[:context].rsplit(" ", 1)[0] + " " if n else ""
                tail = " " + same[-context:].split(" ", 1)[-1] if n < len(ops) - 1 else ""
                same = f"{head}…{tail}"
            out.append(html.escape(same))
            continue
        if i2 > i1:
            out.append(f"<del>{html.escape(''.join(a[i1:i2]))}</del>")
        if j2 > j1:
            out.append(f"<ins>{html.escape(''.join(b[j1:j2]))}</ins>")
    return "".join(out)


def diff_lines(before: str, after: str) -> list[str]:
    """Only the lines that changed between two versions of a file, each as diff_html marks it."""
    a, b = (before or "").split("\n"), (after or "").split("\n")
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        old, new = a[i1:i2], b[j1:j2]
        for k in range(max(len(old), len(new))):
            line = diff_html(old[k] if k < len(old) else "", new[k] if k < len(new) else "", context=80)
            if line.strip():
                out.append(line)
    return out


def _document(conn, work_id: str, run_id: int, kind: str) -> dict | None:
    """The latest version of a reading or bible document that the edition's run made (a steered run
    saves a new version per note), else the work's latest."""
    from house.stages import latest_document
    return latest_document(conn, work_id, kind, run_id)


def analysis(conn, work_id: str, run_id: int, where: dict[str, str] | None = None) -> dict | None:
    """The reading and the bible the edition was drafted under, put for a reader rather than a model:
    the crux (and a second reader's, if the two read it differently), the reading, the voice the run
    drafted in, who everyone is, the style sheet, the narration, the motifs and the hard spots.
    `where` maps a paragraph ID to the paragraph on the page that shows it, so a hard spot can link there."""
    where = where or {}
    reading, bible = _document(conn, work_id, run_id, "reading"), _document(conn, work_id, run_id, "bible")
    if not reading:
        return None
    row = conn.execute("SELECT options FROM run WHERE id=?", (run_id,)).fetchone()
    opts = (row and row["options"]) or {}
    opts = json.loads(opts) if isinstance(opts, str) else opts
    takes = reading.get("voice_takes") or []
    voice = takes[min(int(opts.get("voice") or 0), len(takes) - 1)] if takes else None
    out = {
        "crux": reading.get("crux") or [], "second_crux": reading.get("second_crux") or [],
        "reading": [p.strip() for p in re.split(r"\n\s*\n", reading.get("reading") or "") if p.strip()],
        "voice": RECOMMENDED.sub("", voice["line"]).strip() if voice else None,
        "voice_by": _voice_by(conn, run_id),
        "cast": [], "style": [], "narration": [], "motifs": [], "hard_spots": []}
    if not bible:
        return plain_all(out)
    for c in bible.get("cast") or []:
        # the handle once, then the Japanese (and a romanisation only if it isn't the handle)
        name = " ".join(x for x in (c.get("romanised"), c.get("name_ja")) if x and x != c["handle"])
        out["cast"].append({"handle": c["handle"], "name": name,
                            "role": _sentence(c.get("role", "")), "register": c.get("register", ""),
                            "forms": [{"form": f["form"], "used_by": f.get("used_by", ""), "note": f.get("note") or ""}
                                      for f in c.get("forms") or []]})
    out["style"] = _pairs(bible.get("style_sheet") or {})
    out["narration"] = _pairs(bible.get("narration") or {})
    out["motifs"] = [{"motif": m["motif"], "forms": m.get("source_forms") or [], "why": _sentence(m.get("why", "")),
                      "english": m.get("english", "")} for m in bible.get("motifs") or []]
    # A hard spot links to the paragraph on the page that shows it (the reader merges some), and says
    # which paragraph in words.
    out["hard_spots"] = [{"anchors": [{"id": a, "href": where.get(a), "label": paragraph_label(a)} for a in h.get("anchors") or []],
                          "kind": h.get("kind", ""), "why": h.get("why_hard", "")} for h in bible.get("hard_spots") or []]
    return plain_all(out, cast_names(bible))


def _voice_by(conn, run_id: int) -> str | None:
    """Who rewrote the voices by hand, if anyone did: the voice on the page is then theirs, not keikaku's."""
    from house import steer
    return next((e["by"] for e in reversed(steer.edits(conn, run_id)) if e["file"] == "voices" and e["by"] != "keikaku"), None)


def _sentence(text: str) -> str:
    """The bible's notes are written terse, often lower case and unstopped; on the page, a sentence."""
    text = (text or "").strip()
    if not text:
        return ""
    return text[0].upper() + text[1:] + ("" if text[-1] in ".!?)”’\"'" else ".")


def _pairs(d: dict) -> list[dict]:
    """A style sheet or narration as label and value, the empty ones left out."""
    out = []
    for k, v in d.items():
        if isinstance(v, list):
            v = [str(x) for x in v if x]
            if not v:
                continue
        elif not v:
            continue
        out.append({"label": k.replace("_", " ").capitalize().replace("japanese", "Japanese"), "value": v})
    return out


def _notes(body: dict, i: int, cast: dict[str, str] | None = None) -> list[dict]:
    """A paragraph's notes, once each. Essential notes are the ones the house thought every reader
    needs (those it put in the casual view); the rest are there for the curious."""
    out, seen = [], set()
    for view in VIEWS:
        for n in body["views"][view][i]["notes"]:
            key = (n["anchor"], n["body"])
            if key in seen:
                continue
            seen.add(key)
            out.append({**n, "body": plain(n["body"], cast), "essential": view == "casual", "span_html": n["span"] or ""})
    return out


def ruby_html(seg: dict) -> str:
    """The Japanese paragraph with its furigana, from the parser's tokens."""
    tokens = json.loads(seg["tokens"]) if isinstance(seg["tokens"], str) else seg["tokens"]
    out, plain = [], ""
    for t in tokens:
        if t["t"] in ("note", "layout"):
            continue  # Aozora's editorial notes on the 底本 aren't the author's text and aren't shown
        if t["t"] == "ruby":
            base = "".join(b.get("s", b.get("raw", "")) for b in t["base"])
            out.append(f"<ruby>{html.escape(base)}<rt>{html.escape(t['reading'])}</rt></ruby>")
            plain += base
        elif t["t"] == "odoriji" and t.get("s") == "〳〵" and len(plain) >= 2:
            out.append(html.escape(plain[-2:]))  # the vertical repeat mark, written out for horizontal text
            plain += plain[-2:]
        elif t["t"] == "emph":
            # 傍点 and the like: dots beside the words just before, as the print edition has them
            target = html.escape(t.get("target") or "")
            for k in range(len(out) - 1, -1, -1):
                if target and target in out[k]:
                    head, _, tail = out[k].rpartition(target)
                    out[k] = f'{head}<em class="bouten">{target}</em>{tail}'
                    break
        elif t.get("raw", "").startswith("［＃"):
            continue  # any other notation the parser kept as a token
        else:
            s = t.get("s", t.get("raw", ""))
            out.append(html.escape(s))
            plain += s
    return "".join(out).strip("　 ")


def mark_notes(english: str, notes: list[dict]) -> str:
    """The English, escaped, with each note's span underlined and tappable; a note whose span
    isn't found is still listed in the margin."""
    text = html.escape(english)
    for i, n in enumerate(notes):
        span = html.escape(n["span_html"])
        if span and span in text:
            cls = "t ess" if n["essential"] else "t"
            text = text.replace(span, f'<span class="{cls}" data-note="{i}" tabindex="0" role="button">{span}</span>', 1)
    return text


# Reasons the engine records in its own shorthand (house/stages/desk.py), as a reader should see them.
ENGINE_REASONS = {"the desk's edit didn't match the English":
                  "The edit made for it didn't fit the English as drafted, so it wasn't applied."}


def _query(q: dict, cast: dict[str, str] | None = None) -> dict:
    answer = q["answer"] or {}
    answer = {**answer, "reason": ENGINE_REASONS.get(answer.get("reason", ""), answer.get("reason", ""))}
    return {"number": answer.get("note", ""), "who": READERS.get(q["raised_by"], q["raised_by"]),
            "span": q["span"], "reason": plain(q["reason"], cast), "evidence": [RUBY.sub("", e) for e in q["evidence"] or []],
            "recommendation": plain(q["recommendation"], cast), "confidence": plain(q["confidence"], cast),
            "status": q["status"], "outcome": OUTCOMES.get(q["status"], q["status"]),
            "desk": plain(answer.get("reason", ""), cast)}


def _decisions(queries: list[dict]) -> list[dict]:
    """The paragraph's queries grouped by the decision that answered them. One change often answers
    several notes, and the desk gives its reason once per change, so it's shown once."""
    groups = {}
    for q in queries:
        key = (q["status"], q["desk"]) if q["desk"] else (q["status"], q["number"])
        groups.setdefault(key, {"status": q["status"], "outcome": DECIDED.get(q["status"], q["status"]),
                                "reason": q["desk"], "queries": []})["queries"].append(q)
    return list(groups.values())


def _meta(conn, work_id: str) -> dict:
    row = dict(conn.execute("SELECT * FROM work WHERE id=?", (work_id,)).fetchone())
    try:
        reg = works.info(work_id, conn)
    except KeyError:
        reg = {}
    # works.json is the rights record as it stands now; the copy taken when the work was fetched may be older
    # (for a work added from a link, both are the record read from its card)
    rights = row["rights"]
    rights = reg.get("rights") or (json.loads(rights) if isinstance(rights, str) else rights or {})
    # No English title or author is "": templates show the Japanese alone (a work whose card call failed)
    title_en = row["title_en"] or reg.get("title_en") or ""
    author_en = row["author_en"] or reg.get("author_en") or ""
    return {"id": work_id, "title": row["title"], "title_en": "" if title_en == row["title"] else title_en,
            "author": row["author"], "author_en": "" if author_en == row["author"] else author_en,
            "card_url": row["card_url"] or reg.get("card_url"), "colophon": row["colophon"], "rights": rights,
            "blurb": reg.get("blurb"), "about": reg.get("about")}


def _overall(labels: list[str]) -> str:
    return min(labels, key=LABELS.index) if labels else "draft"


def _rows(conn, sql: str, run_id: int, json_cols: tuple) -> list[dict]:
    out = []
    for r in conn.execute(sql, (run_id,)):
        d = dict(r)
        for k in json_cols:
            if isinstance(d.get(k), str):
                d[k] = json.loads(d[k])
        out.append(d)
    return out


def _date(stamp: str | None) -> str:
    """'2026-11-01 23:32:25' → '1 Nov 2026'."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", stamp or "")
    if not m:
        return ""
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    return f"{int(m.group(3))} {months[int(m.group(2)) - 1]} {m.group(1)}"
