"""What several stages share: the cached prefix for a call about a page, the current English, and which model an option names."""

import json
import re

from house import context
from house.db import dumps
from house.client import SPARK, WONDER

MODELS = {"spark": SPARK, "wonder": WONDER}
# What a run uses unless told otherwise: the best set-up the experiments found (docs/experiments/).
# The final read runs on Wonder: judged blind on three texts, it made twice Spark's meaning fixes (experiment 10).
DEFAULTS = {"draft_model": "spark", "draft_prompt": "translate-draft-plain", "reader_model": "spark",
            "desk_model": "wonder", "final_model": "wonder", "copy_model": "spark"}


def model(ctx, option: str) -> str:
    """The model a run option names, 'spark' or 'wonder', or the default for it."""
    name = ctx.options.get(option) or DEFAULTS[option]
    if name not in MODELS:
        raise ValueError(f"{option} must be one of {', '.join(MODELS)}, not {name!r}")
    return MODELS[name]


def stable(ctx, around=None) -> str:
    """The cached prefix for a call about a page: the reading, the bible, and as much of the source
    as the length of the work allows (context.source_text)."""
    bible = ctx.latest("bible")
    return context.join(context.reading(ctx.latest("reading")), context.bible(bible),
                        context.source_text(ctx.work, around, bible.get("chapter_summaries")))


def latest_units(ctx) -> dict[tuple, str]:
    """The current English per unit: a paragraph, or a group the drafter joined, keyed by its ids."""
    units = {}
    for r in ctx.conn.execute("SELECT segment_ids, english FROM revision WHERE run_id=? AND variant='lead' ORDER BY id",
                              (ctx.run_id,)):
        ids = tuple(json.loads(r["segment_ids"]))
        for k in [k for k in units if set(k) & set(ids) and k != ids]:
            del units[k]  # a later unit over the same paragraphs replaces an earlier one
        units[ids] = r["english"]
    return units


def unit_of(units: dict[tuple, str], label: str) -> tuple | None:
    """The unit a model named: 'p12', or a group written 'p21-p23', 'p21–p23' or 'p21, p22, p23'."""
    for ids in units:
        names = {ids[0], "–".join((ids[0], ids[-1])), "-".join((ids[0], ids[-1])), ", ".join(ids), ",".join(ids)}
        if label.strip() in names:
            return ids
    found = next((ids for ids in units if label.strip() in ids), None)
    whole = re.fullmatch(r"(p\d+)\s*[-–,]\s*p\d+.*", label.strip())
    if found is None and whole:  # a range the drafter didn't group: its first paragraph
        return next((ids for ids in units if whole.group(1) in ids), None)
    if found is None:  # a model that wrote "change to p4: ..." still named p4; take the first ID it gives
        m = re.search(r"\bp\d+(?:\s*[-–]\s*p\d+)?", label)
        if m and m.group(0) != label.strip():
            return unit_of(units, re.sub(r"\s*([-–])\s*", r"\1", m.group(0)))
    return found


def latest_english(ctx) -> dict[str, str]:
    """The current English per paragraph, from latest_units; a paragraph in a group the drafter joined
    carries the group's English, marked as such."""
    out = {}
    for ids, en in latest_units(ctx).items():
        for i in ids:
            out[i] = en if len(ids) == 1 else f"[grouped with {', '.join(ids)}] {en}"
    return out


def translator_notes(ctx, pid: str) -> list[str]:
    """The translator's notes on a paragraph's draft (later revisions carry none)."""
    row = ctx.conn.execute("SELECT notes FROM revision WHERE run_id=? AND variant='lead' AND segment_ids LIKE ? "
                           "AND notes IS NOT NULL ORDER BY id DESC LIMIT 1", (ctx.run_id, f'%"{pid}"%')).fetchone()
    return json.loads(row["notes"]) if row else []


def apply_edit(text: str, find: str, replace: str) -> str | None:
    """One exact find-and-replace, as an editor's tool does it: the words must appear once. A quoted
    span copied with its quotation marks, or with stray spaces, is matched without them."""
    for f, r in ((find, replace), (find.strip(), replace.strip()), (find.strip().strip("“”\"‘’'"), replace.strip().strip("“”\"‘’'"))):
        if f and text.count(f) == 1:
            return text.replace(f, r)
    return None


def locked_lines(ctx) -> set[str]:
    return {r["segment_id"] for r in ctx.conn.execute("SELECT segment_id FROM lock WHERE work_id=?", (ctx.work_id,))}


EDIT_TOOL = {
    "type": "function", "name": "edit", "strict": True,
    "description": ("Replace words in the house's English. `old` must be the exact words as they stand now, and appear "
                    "exactly once in the text you were given, unless replace_all is true, which changes every place they "
                    "appear. If they appear more than once, or not at all, nothing changes and you're told where they are: "
                    "include more of the surrounding words to pick one. An edit stays inside one paragraph."),
    "parameters": {"type": "object", "additionalProperties": False,
                   "required": ["old", "new", "reason", "replace_all"],
                   "properties": {"old": {"type": "string", "description": "The exact words to replace"},
                                  "new": {"type": "string", "description": "What goes in their place"},
                                  "reason": {"type": "string", "description": "Why, in a sentence"},
                                  "replace_all": {"type": "boolean", "description": "Change every place they appear"}}},
}


FIND_TOOL = {
    "type": "function", "name": "find", "strict": True,
    "description": "Where some words appear in the house's English: each paragraph, with the words around them. Changes nothing.",
    "parameters": {"type": "object", "additionalProperties": False, "required": ["words"],
                   "properties": {"words": {"type": "string", "description": "The exact words to look for"}}},
}


def edit_tool(answers: bool = False) -> dict:
    """The one edit tool the desk, the final read and the copy editor share. The desk also says
    which readers' notes an edit answers."""
    if not answers:
        return EDIT_TOOL
    tool = json.loads(json.dumps(EDIT_TOOL))
    tool["parameters"]["properties"]["answers"] = {"type": "array", "items": {"type": "string"},
                                                   "description": "The labels of the notes this edit answers (F1, R2...); empty if none"}
    tool["parameters"]["required"].append("answers")
    return tool


def label(unit: tuple) -> str:
    return unit[0] if len(unit) == 1 else f"{unit[0]}–{unit[-1]}"


class Editor:
    """Runs the edit tool on the units a call was given, as an editor's tool does: the words must be
    found exactly once (or replace_all), an edit never crosses a paragraph, and a locked line is never
    changed. A refusal goes back to the model with what it found, so it can try again."""

    def __init__(self, ctx, units: dict[tuple, str], ids: set[str] | None = None):
        self.locked = locked_lines(ctx)
        self.before = {u: en for u, en in units.items() if ids is None or u[0] in ids}
        self.text = dict(self.before)
        self.applied: dict[tuple, list[dict]] = {}
        self.refused = 0

    def hits(self, old: str) -> list[tuple[tuple, int]]:
        return [(u, en.count(old)) for u, en in self.text.items() if old and old in en]

    def where(self, old: str, hits) -> str:
        out = []
        for u, n in hits[:12]:
            en, i = self.text[u], self.text[u].index(old)
            out.append(f"{label(u)}{f' ({n} times)' if n > 1 else ''}: “…{en[max(0, i - 40):i + len(old) + 40]}…”")
        return "; ".join(out) + (f"; and {len(hits) - 12} more paragraphs" if len(hits) > 12 else "")

    def __call__(self, name: str, args: dict) -> str:
        if name == "find":
            hits = self.hits(args.get("words") or "")
            return (f"{sum(n for _, n in hits)} times: {self.where(args['words'], hits)}" if hits else "Not found.")
        if name != "edit":
            self.refused += 1
            return f"Error: there is no tool called {name}."
        old, new = args.get("old") or "", args.get("new") or ""
        hits = self.hits(old)
        if not hits:  # a span quoted with its quotation marks, or with stray spaces
            quotes = "“”\"‘’'"
            for alt_old, alt_new in ((old.strip(), new.strip()), (old.strip().strip(quotes), new.strip().strip(quotes))):
                if self.hits(alt_old):
                    old, new, hits = alt_old, alt_new, self.hits(alt_old)
                    break
        total = sum(n for _, n in hits)
        if old == new:
            self.refused += 1
            return "Error: old and new are the same."
        if not total:
            self.refused += 1
            return ("Error: not found. Quote the English exactly as it stands now, with its punctuation; an earlier edit "
                    "may have changed it. An edit can't cross from one paragraph into the next.")
        if total > 1 and not args.get("replace_all"):
            self.refused += 1
            return f"Error: found {total} times, so nothing changed: {self.where(old, hits)}. Include more of the surrounding words, or set replace_all."
        locked = [u for u, _ in hits if set(u) & self.locked]
        done = []
        for u, n in hits:
            if u in locked:
                continue
            self.text[u] = self.text[u].replace(old, new)
            self.applied.setdefault(u, []).append({**args, "old": old, "new": new})
            done.append(label(u))
        if not done:
            self.refused += 1
            return f"Error: {', '.join(label(u) for u in locked)} is locked by the editor and can't change."
        skipped = f" Not in {', '.join(label(u) for u in locked)}, which the editor has locked." if locked else ""
        return f"Done: {total - sum(n for u, n in hits if u in locked)} replaced, in {', '.join(done)}.{skipped}"

    def edited(self) -> dict[tuple, dict]:
        """{unit: {"english", "applied": [the edits that went in]}} for the units that changed."""
        return {u: {"english": self.text[u], "applied": self.applied[u]} for u in self.applied if self.text[u] != self.before[u]}


def change_flags(old: str, new: str) -> list[str]:
    """What code checks on a changed paragraph: no stray script, and not shrunk (words gone missing)."""
    from house import checks
    flags = checks.stray_scripts(new)
    if len(new) < 0.7 * len(old):
        flags.append(f"paragraph shrank to {len(new) / max(len(old), 1):.0%} of its length")
    return flags


def new_revision(ctx, unit: tuple, english: str, cause: dict, actor: str) -> int:
    v = ctx.conn.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM revision WHERE run_id=? AND segment_ids=? AND variant='lead'",
                         (ctx.run_id, dumps(list(unit)))).fetchone()[0]
    cur = ctx.conn.execute("INSERT INTO revision (run_id, work_id, segment_ids, version, english) VALUES (?,?,?,?,?)",
                           (ctx.run_id, ctx.work_id, dumps(list(unit)), v, english))
    eid = ctx.emit(actor, "revision.created", {"segment_id": unit[0], "ids": list(unit), "revision_id": cur.lastrowid, "version": v,
                                               "english": english, "cause": cause})
    ctx.conn.execute("UPDATE revision SET event_id=? WHERE id=?", (eid, cur.lastrowid))
    ctx.conn.commit()
    return cur.lastrowid
