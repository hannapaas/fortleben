"""Steering a run at the checkpoint (docs/STEERING.md): an editor's note goes to the model that wrote
the reading, which carries it into the reading and the bible as house style and replies; page 1 is then
drafted again under the amended bible, so the effect shows as English. The loop ends when the editor
approves, never on the house's decision.

steer(conn, client, run_id, note) runs one round; approve(conn, run_id, voice) records the voice and
queues the run, which whoever called it resumes from the draft. edit(conn, run_id, file, text, by) is the
other way to steer: the editor rewrites the reading, the voices or the bible by hand, and every later call
reads their version.
"""

import hashlib
import json
import re
from pathlib import Path

from house import context, events
from house.client import WONDER, Call, load_schema
from house.db import dumps
from house.orchestrator import context_for
from house.stages import bible as bible_stage
from house.stages import checkpoint, latest_document
from house.stages.draft import voice_take

ACTOR = "first-read"  # the department that wrote the reading answers for it
READING_FIELDS = [k for k in load_schema("first-read")["properties"] if k != "say"]
BIBLE_FIELDS = [k for k in load_schema("analyst-bible")["properties"] if k != "say"]


class NotWaiting(Exception):
    """The run isn't waiting at the checkpoint, so there is nothing to steer or approve."""


def waiting(conn, run_id: int) -> dict:
    """The run's checkpoint document, if the run is waiting at it; NotWaiting otherwise, in plain words."""
    row = conn.execute("SELECT status FROM run WHERE id=?", (run_id,)).fetchone()
    if not row:
        raise NotWaiting(f"there is no run {run_id}")
    doc, _ = checkpoint.document(conn, run_id)
    if row["status"] != "waiting" or doc is None:
        raise NotWaiting(f"run {run_id} isn't waiting at the checkpoint (it is {row['status']})")
    return doc


def current_voice(ctx) -> int:
    takes = ctx.latest("reading")["voice_takes"]
    return min(int(ctx.options.get("voice") or 0), len(takes) - 1)


def current_page(doc: dict, voice: int) -> list[list[str]]:
    """Page 1 as it stands in this voice: the editor's own version of it, else the last round's redraft in it,
    else the take. A note that redrafts the voice's page replaces the editor's version (`steer`)."""
    if (doc.get("edited") or {}).get(str(voice)):
        return doc["edited"][str(voice)]
    for r in reversed(doc["rounds"]):
        if r.get("voice", 0) == voice:
            return r["english"]
    return doc["takes"][min(voice, len(doc["takes"]) - 1)]["english"]


def page_block(ctx, take: dict, english: list[list[str]]) -> str:
    ja = {p.id: p.model_text.strip("　 ") for p in ctx.work.translatable()}
    rows = []
    for pid, en in english:
        first = pid.split("–")[0]
        rows.append(f"{pid}　{ja.get(first, '')}\n{pid}　{en}")
    return context.block(f"Page 1 as drafted now, in the voice “{take['label']}: {take['line']}”: the Japanese, then the English",
                         "\n\n".join(rows))


def rounds_block(rounds: list[dict]) -> str:
    if not rounds:
        return ""
    out = []
    for n, r in enumerate(rounds, 1):
        out.append(f"Note {n}, quoted:\n\n{quote(r['note'])}\n\nYour reply: {r['reply']}"
                   + (f"\nWhat you changed: {'; '.join(r['changed'])}" if r["changed"] else "\nYou changed nothing.")
                   + (f"\nYou asked: {r['question']}" if r.get("question") else ""))
    return context.block("The notes so far, and your replies", "\n\n".join(out))


def quote(text: str) -> str:
    return "\n".join(f"> {line}" for line in text.strip().splitlines() or [""])


def rewritten(doc: dict, kind: str) -> str:
    """A reading or bible the editor rewrote by hand: what every call reads in place of the stored one, so a
    note is read against it and the amended version returned carries it."""
    if not doc.get("edited_text"):
        return ""
    return context.block(f"The {kind} as it now reads, rewritten by hand. Where it differs from the stored {kind} above, "
                         f"this version stands, and the {kind} you return carries it", doc["edited_text"])


def replaced(ctx, kind: str, old: dict, new: dict) -> None:
    """A note's amended reading or bible took the place of the editor's hand edit: recorded like an edit, by
    keikaku, so what every later call reads is never changed without a trace."""
    if old.get("edited_text"):
        after = _norm(context.bible_text(new) if kind == "bible" else context.reading_text(new))
        ctx.emit("keikaku", "document.edited", {"file": kind, "before": old["edited_text"], "after": after, "by": "keikaku",
                                                "cause": "note", "diff": edition_diff(old["edited_text"], after)})


def edition_diff(before: str, after: str) -> list[str]:
    from house.edition import diff_lines
    return diff_lines(before, after)


def fields(body: dict, keys: list[str]) -> dict:
    return {k: body.get(k) for k in keys}


def steer(conn, client, run_id: int, note: str) -> dict:
    """One round: the note is carried into the reading and the bible, new versions are saved where they
    changed, page 1 is drafted again in the current voice, and the round is appended to the checkpoint
    document. The run stays waiting. Returns the round."""
    note = (note or "").strip()
    if not note:
        raise ValueError("the note is empty")
    doc = waiting(conn, run_id)
    ctx = context_for(conn, client, run_id)
    ctx.options["_stage"] = "checkpoint"
    stored = conn.execute("SELECT cap_usd FROM run WHERE id=?", (run_id,)).fetchone()
    if not client.budget.cap_given and stored["cap_usd"]:
        client.budget.run_cap = stored["cap_usd"]  # a round is spent against the run's own cap
    reading, bible = ctx.latest("reading"), ctx.latest("bible")
    voice = current_voice(ctx)
    take = reading["voice_takes"][voice]
    second = (context.block("A second reader's crux, which stands beside the reading until it is ruled on",
                            "\n".join(f"- {c['point']} {c['why']} For the English: {c['for_the_english']}"
                                      for c in reading["second_crux"])) if reading.get("second_crux") else "")
    inp = context.join(
        context.work_card(ctx.work),
        context.block("The house's reading, as stored", json.dumps(fields(reading, READING_FIELDS), ensure_ascii=False, indent=1)),
        rewritten(reading, "reading"),
        second,
        context.block("The story bible, as stored", json.dumps(fields(bible, BIBLE_FIELDS), ensure_ascii=False, indent=1)),
        rewritten(bible, "bible"),
        page_block(ctx, take, current_page(doc, voice)),
        rounds_block(doc["rounds"]),
        context.block("The new note, quoted: the person's own words, to interpret", quote(note)),
    )
    res = ctx.call(ACTOR, Call("steer", WONDER, "medium", inp, load_schema("steer"), f"{ctx.work_id}:steer",
                               expected_output_tokens=12000))
    out = res.data

    reading_v, bible_v = ctx.version("reading"), ctx.version("bible")
    if fields(out["reading"], READING_FIELDS) != fields(reading, READING_FIELDS):
        new = {**reading, **fields(out["reading"], READING_FIELDS)}  # keeps the second crux and the head's line
        new.pop("edited_text", None)  # a hand edit is carried into the fields the reply returns
        eid = ctx.emit(ACTOR, "reading.written", {"version": reading_v + 1, "crux": new["crux"], "cause": "steer"},
                       call_id=res.call_id)
        reading_v = ctx.save("reading", new, eid)
        replaced(ctx, "reading", reading, new)
    if fields(out["bible"], BIBLE_FIELDS) != fields(bible, BIBLE_FIELDS):
        new = {**bible, **fields(out["bible"], BIBLE_FIELDS)}
        new.pop("edited_text", None)
        new["chapter_summaries"] = bible_stage.chapter_summaries(ctx, new)
        eid = ctx.emit(ACTOR, "bible.written", {"version": bible_v + 1, "cast": len(new["cast"]),
                                                "motifs": len(new["motifs"]), "cause": "steer"}, call_id=res.call_id)
        bible_v = ctx.save("bible", new, eid)
        replaced(ctx, "bible", bible, new)

    take = voice_take(ctx)  # the amended reading may have reworded or reordered the takes
    rnd = {"note": note, "reply": out["reply"], "changed": out["changed"], "question": out["question"] or None,
           "reading_version": reading_v, "bible_version": bible_v, "voice": voice,
           "take": {"label": take["label"], "line": take["line"]},
           "english": checkpoint.draft_first_page(ctx, take)}
    eid = ctx.emit("house", "checkpoint.steered", rnd, call_id=res.call_id)
    edited = dict(doc.get("edited") or {})
    mine = edited.pop(str(voice), None)
    ctx.save("checkpoint", {**doc, "rounds": doc["rounds"] + [rnd], "edited": edited}, eid)
    if mine:  # the editor's page 1 in this voice gave way to the redraft: recorded, like a replaced file
        before, after = page_text(mine), page_text(rnd["english"])
        ctx.emit("keikaku", "document.edited", {"file": "page", "voice": voice, "label": take["label"], "before": before,
                                                "after": after, "by": "keikaku", "cause": "note", "diff": edition_diff(before, after)})
    return rnd


def approve(conn, run_id: int, voice: int) -> None:
    """The editor approves the checkpoint in a voice: recorded in the run's options, the run queued.
    Whoever called this resumes it from the draft."""
    waiting(conn, run_id)
    row = conn.execute("SELECT work_id, options FROM run WHERE id=?", (run_id,)).fetchone()
    takes = latest_document(conn, row["work_id"], "reading", run_id)["voice_takes"]
    if not 0 <= int(voice) < len(takes):
        raise ValueError(f"there are {len(takes)} voices, numbered 0 to {len(takes) - 1}; there is no voice {voice}")
    options = {**json.loads(row["options"] or "{}"), "voice": int(voice)}
    conn.execute("UPDATE run SET options=?, status='queued' WHERE id=?", (dumps(options), run_id))
    events.emit(conn, run_id, "editor", "checkpoint.approved", {"voice": int(voice), "take": takes[int(voice)]})


# --- the files: what every stage after the checkpoint reads, which the editor can rewrite by hand -----------
# The reading and the bible reach every call as context.reading and context.bible write them, and the voice as
# its name and line. Those are the files. An editor's own version of the reading or the bible is kept as the
# document's `edited_text` and read in place of the stored fields; the voices are parsed back into the reading.
# Every edit is a new version of the document with a `document.edited` event holding before and after.

FILES = {"reading": "reading.md", "voices": "voices.md", "bible": "bible.md"}
_VOICE = re.compile(r"^##\s+Voice\s+(\d+)\s*:[ \t]*(.*?)[ \t]*$", re.M)
WRITTEN = ".written.json"  # which run the terminal's files are for, and a hash of each as written


def voices_text(takes: list[dict]) -> str:
    return "\n\n".join(f"## Voice {n}: {t['label']}\n\n{t['line']}" for n, t in enumerate(takes))


def texts(reading: dict, bible: dict) -> dict[str, str]:
    """The three files as they stand: the reading and the bible as every call reads them, and the voices."""
    return {"reading": context.reading_text(reading), "voices": voices_text(reading["voice_takes"]),
            "bible": context.bible_text(bible)}


def _norm(text: str) -> str:
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip().split("\n")
    return "\n".join(line.rstrip() for line in lines)


def parse_voices(text: str, takes: list[dict]) -> list[dict]:
    """The voice takes with the names and lines a voices file gives them: '## Voice N: name', then the line
    (in voices.md, the italic line under the heading). Every voice has to be there, once."""
    marks = list(_VOICE.finditer(text))
    found = {}
    for i, m in enumerate(marks):
        body = text[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(text)].strip()
        line = re.split(r"\n\s*\n", body, maxsplit=1)[0].strip()
        line = re.sub(r"^([*_])(.+)\1$", r"\2", line, flags=re.S).strip()
        found.setdefault(int(m.group(1)), (m.group(2).strip(), " ".join(line.split())))
    if sorted(found) != list(range(len(takes))):
        raise ValueError(f"keep one heading per voice, from '## Voice 0: …' to '## Voice {len(takes) - 1}: …', "
                         "each with its line under it")
    out = []
    for n, t in enumerate(takes):
        label, line = found[n]
        if not label or not line:
            raise ValueError(f"voice {n} needs a name after its heading and a line under it")
        out.append({**t, "label": label, "line": line})
    return out


def edit(conn, run_id: int, name: str, text: str, by: str, person_id: int | None = None) -> bool:
    """The editor rewrites one file by hand while the run waits at the checkpoint, and every later call reads
    their version. Saved as a new version of the reading or the bible, in one transaction with the
    `document.edited` event that keeps before, after and who. False if it reads as it did."""
    if name not in FILES:
        raise ValueError(f"there is no file called {name!r}")
    waiting(conn, run_id)
    ctx = context_for(conn, None, run_id)
    reading, bible = ctx.latest("reading"), ctx.latest("bible")
    before = _norm(texts(reading, bible)[name])
    text = _norm(text)
    if not text:
        raise ValueError("the file is empty")
    own = len(texts(*({k: v for k, v in d.items() if k != "edited_text"} for d in (reading, bible)))[name])
    if len(text) > max(3 * own, 6000):  # every later call carries it, so it can't grow without end
        raise ValueError(f"keep it to {max(3 * own, 6000):,} characters, three times what keikaku wrote")
    if name == "voices":
        kind, new = "reading", {**reading, "voice_takes": parse_voices(text, reading["voice_takes"])}
        after = voices_text(new["voice_takes"])
    else:
        kind, doc = name, reading if name == "reading" else bible
        new, after = {k: v for k, v in doc.items() if k != "edited_text"}, text
        stored = context.reading_text(new) if name == "reading" else context.bible_text(new)
        if after != _norm(stored):
            new["edited_text"] = after  # put back as it was, it is the stored version again
    if after == before:
        return False
    eid = events.emit(conn, run_id, "editor", "document.edited",
                      {"file": name, "before": before, "after": after, "by": by, "person_id": person_id,
                       "diff": edition_diff(before, after)}, commit=False)
    ctx.save(kind, new, eid)  # commits both
    return True


def page_text(english: list[list[str]]) -> str:
    return "\n\n".join(en for _, en in english)


def edit_page(conn, run_id: int, voice, text: str, by: str, person_id: int | None = None) -> bool:
    """The editor rewrites page 1 in one voice while the run waits: paragraph by paragraph, with a blank line
    between, as many as the page has. If the run is approved in that voice, the draft takes this page as its
    first page instead of drafting it, and every later page follows it as the voice to match. Kept in the
    checkpoint document with a `document.edited` event (file "page"). False if it reads as it did."""
    doc = waiting(conn, run_id)
    if isinstance(voice, bool) or not isinstance(voice, int) or not 0 <= voice < len(doc["takes"]):
        raise ValueError("there's no such voice")
    page = current_page(doc, voice)
    paras = [" ".join(p.split()) for p in re.split(r"\n\s*\n", _norm(text)) if p.strip()]
    if len(paras) != len(page):
        raise ValueError(f"keep page 1 to its {len(page)} paragraphs, with a blank line between each")
    before, after = page_text(page), "\n\n".join(paras)
    if after == before:
        return False
    if len(after) > max(3 * len(before), 6000):
        raise ValueError("keep page 1 to about the length keikaku drafted it")
    ctx = context_for(conn, None, run_id)
    label = ctx.latest("reading")["voice_takes"][min(voice, len(ctx.latest("reading")["voice_takes"]) - 1)]["label"]
    eid = events.emit(conn, run_id, "editor", "document.edited",
                      {"file": "page", "voice": voice, "label": label, "before": before, "after": after, "by": by,
                       "person_id": person_id, "diff": edition_diff(before, after)}, commit=False)
    edited = {**(doc.get("edited") or {}), str(voice): [[pid, en] for (pid, _), en in zip(page, paras)]}
    ctx.save("checkpoint", {**doc, "edited": edited}, eid)  # commits both
    return True


def edits(conn, run_id: int) -> list[dict]:
    """Every hand edit of the files a run was drafted from, oldest first: file, before, after, by, when."""
    return [{**json.loads(r["payload"]), "at": r["created_at"]} for r in conn.execute(
        "SELECT payload, created_at FROM event WHERE run_id=? AND type='document.edited' ORDER BY id", (run_id,))]


# --- the checkpoint as Markdown, for the terminal and an assistant reading it to someone -----------------

def _sha(text: str) -> str:
    return hashlib.sha256(_norm(text).encode("utf-8")).hexdigest()


def _written(folder: Path) -> dict:
    try:
        return json.loads((folder / WRITTEN).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def untaken(folder: Path) -> list[str]:
    """Files changed by hand since they were written that `read_back` didn't take: written for another run,
    or for a run that is no longer waiting."""
    written = _written(folder)
    return [f for f, h in (written.get("files") or {}).items()
            if (folder / f).exists() and _sha((folder / f).read_text(encoding="utf-8")) != h]


def write(conn, run_id: int, folder: Path) -> tuple[list[Path], list[Path]]:
    """Write reading.md, bible.md and voices.md into `folder`, with a note of the run they're for, so
    `read_back` takes only what was changed by hand since, and only for that run. A hand edit that wasn't
    taken is moved aside to <name>.unused.md rather than written over. Returns the files and what was moved."""
    folder.mkdir(parents=True, exist_ok=True)
    moved = []
    for f in untaken(folder):
        (folder / f).replace(folder / f.replace(".md", ".unused.md"))
        moved.append(folder / f.replace(".md", ".unused.md"))
    paths, hashes = [], {}
    for name, text in markdown(conn, run_id).items():
        (folder / name).write_text(text, encoding="utf-8")
        paths.append(folder / name)
        hashes[name] = _sha(text)
    (folder / WRITTEN).write_text(json.dumps({"run": run_id, "files": hashes}), encoding="utf-8")
    return paths, moved


def _untitled(text: str) -> str:
    """A reading.md or bible.md without the title line `markdown` puts on it."""
    lines = text.replace("\r\n", "\n").split("\n")
    return "\n".join(lines[1:]) if lines and lines[0].startswith("# ") else text


def read_back(conn, run_id: int, folder: Path, by: str = "the editor") -> list[str]:
    """The files in `folder` that were changed by hand since `write` wrote them for this run, saved as the
    editor's version (`edit`). Returns their names. Files written for another run are left alone."""
    written = _written(folder)
    if written.get("run") != run_id:
        return []
    changed = []
    for name, fname in FILES.items():
        path = folder / fname
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if _sha(text) == written["files"].get(fname):
            continue
        try:
            if edit(conn, run_id, name, text if name == "voices" else _untitled(text), by):
                changed.append(fname)
        except ValueError as e:
            raise ValueError(f"{fname}: {e}" + (f" ({', '.join(changed)} saved)" if changed else "")) from e
        written["files"][fname] = _sha(text)  # taken: not taken again, nor moved aside
        (folder / WRITTEN).write_text(json.dumps(written), encoding="utf-8")
    return changed


def markdown(conn, run_id: int) -> dict[str, str]:
    """reading.md, bible.md and voices.md for a run with a checkpoint: what `keikaku checkpoint` writes.
    reading.md and bible.md are, under their titles, exactly what every later call reads; voices.md gives
    each voice's name in its heading and its line in italics under it, then page 1 in that voice."""
    doc, _ = checkpoint.document(conn, run_id)
    if doc is None:
        raise NotWaiting(f"run {run_id} has no checkpoint: it was started without --checkpoint, or hasn't reached it")
    ctx = context_for(conn, None, run_id)
    reading, bible = ctx.latest("reading"), ctx.latest("bible")
    title = f"{ctx.work.title} ({ctx.work.meta.get('title_en', '')}), by {ctx.work.author}"
    ja = {p.id: p.model_text.strip("　 ") for p in ctx.work.translatable()}
    voice = current_voice(ctx)

    def page(english):
        return "\n\n".join(en for _, en in english)

    v = [f"# Page 1 in each voice: {title}", "",
         "The same page drafted once in each voice the reading offers. Nothing else has been drafted. "
         "A voice's name (in its heading) and its line (in italics under it) are what the draft is told; edit them "
         "here and the draft reads yours.", ""]
    for n, t in enumerate(reading["voice_takes"]):
        drafted = doc["takes"][n]["english"] if n < len(doc["takes"]) else []
        v += [f"## Voice {n}: {t['label']}", "", f"*{t['line']}*", "", page(drafted), ""]
    for n, rnd in enumerate(doc["rounds"], 1):
        t = rnd.get("take") or doc["takes"][rnd.get("voice", 0)]
        v += [f"### Note {n}", "", "\n".join(f"> {line}" for line in rnd["note"].splitlines()), "",
              f"**The house's reply:** {rnd['reply']}", ""]
        if rnd["changed"]:
            v += ["**What changed:**", ""] + [f"- {c}" for c in rnd["changed"]] + [""]
        if rnd.get("question"):
            v += [f"**The house asks:** {rnd['question']}", ""]
        v += [f"**Page 1 again, in voice {rnd.get('voice', 0)} ({t['label']}):**", "", page(rnd["english"]), ""]
    first = doc["takes"][0]["english"]
    v += ["### Page 1 in Japanese", "", "\n\n".join(ja.get(pid.split("–")[0], "") for pid, _ in first), ""]
    v += [f"The draft will be written in voice {voice} unless you approve another."]

    return {"reading.md": f"# The house's reading: {title}\n\n{context.reading_text(reading).strip()}\n",
            "bible.md": f"# The analysis: {title}\n\n{context.bible_text(bible).strip()}\n",
            "voices.md": "\n".join(v) + "\n"}
