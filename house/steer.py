"""Steering a run at the checkpoint (docs/STEERING.md): an editor's note goes to the model that wrote
the reading, which carries it into the reading and the bible as house style and replies; page 1 is then
drafted again under the amended bible, so the effect shows as English. The loop ends when the editor
approves, never on the house's decision.

steer(conn, client, run_id, note) runs one round; approve(conn, run_id, voice) records the voice and
queues the run, which whoever called it resumes from the draft.
"""

import json

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
    """Page 1 as it stands in this voice: the last round's redraft in it, else the take."""
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
        second,
        context.block("The story bible, as stored", json.dumps(fields(bible, BIBLE_FIELDS), ensure_ascii=False, indent=1)),
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
        eid = ctx.emit(ACTOR, "reading.written", {"version": reading_v + 1, "crux": new["crux"], "cause": "steer"},
                       call_id=res.call_id)
        reading_v = ctx.save("reading", new, eid)
    if fields(out["bible"], BIBLE_FIELDS) != fields(bible, BIBLE_FIELDS):
        new = {**bible, **fields(out["bible"], BIBLE_FIELDS)}
        new["chapter_summaries"] = bible_stage.chapter_summaries(ctx, new)
        eid = ctx.emit(ACTOR, "bible.written", {"version": bible_v + 1, "cast": len(new["cast"]),
                                                "motifs": len(new["motifs"]), "cause": "steer"}, call_id=res.call_id)
        bible_v = ctx.save("bible", new, eid)

    take = voice_take(ctx)  # the amended reading may have reworded or reordered the takes
    rnd = {"note": note, "reply": out["reply"], "changed": out["changed"], "question": out["question"] or None,
           "reading_version": reading_v, "bible_version": bible_v, "voice": voice,
           "take": {"label": take["label"], "line": take["line"]},
           "english": checkpoint.draft_first_page(ctx, take)}
    eid = ctx.emit("house", "checkpoint.steered", rnd, call_id=res.call_id)
    ctx.save("checkpoint", {**doc, "rounds": doc["rounds"] + [rnd]}, eid)
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


# --- the checkpoint as Markdown, for the terminal and an assistant reading it to someone -----------------

def markdown(conn, run_id: int) -> dict[str, str]:
    """reading.md, bible.md and voices.md for a run with a checkpoint: what `keikaku checkpoint` writes."""
    doc, _ = checkpoint.document(conn, run_id)
    if doc is None:
        raise NotWaiting(f"run {run_id} has no checkpoint: it was started without --checkpoint, or hasn't reached it")
    ctx = context_for(conn, None, run_id)
    reading, bible = ctx.latest("reading"), ctx.latest("bible")
    title = f"{ctx.work.title} ({ctx.work.meta.get('title_en', '')}), by {ctx.work.author}"
    ja = {p.id: p.model_text.strip("　 ") for p in ctx.work.translatable()}
    voice = current_voice(ctx)

    r = [f"# The house's reading: {title}", ""]
    r += ["## The crux", ""] + [f"- **{c['point']}** {c['why']} *For the English:* {c['for_the_english']}" for c in reading["crux"]]
    if reading.get("second_crux"):
        r += ["", "## A second reader's crux", "", "A second reader, who never saw the reading, put it this way:", ""]
        r += [f"- **{c['point']}** {c['why']} *For the English:* {c['for_the_english']}" for c in reading["second_crux"]]
    r += ["", "## The reading", "", reading["reading"]]
    if reading.get("open_questions"):
        r += ["", "## Open questions", ""] + [f"- {q['question']} {q.get('why_it_matters') or ''}".rstrip() for q in reading["open_questions"]]
    r += ["", "## The voices", "", "The draft is written in the voice you approve (`--voice N`); the first is the house's choice.", ""]
    r += [f"- **{n}. {t['label']}**: {t['line']}" for n, t in enumerate(reading["voice_takes"])]

    def page(english):
        return "\n\n".join(en for _, en in english)

    v = [f"# Page 1 in each voice: {title}", "",
         "The same page drafted once in each voice the reading offers. Nothing else has been drafted.", ""]
    for n, t in enumerate(doc["takes"]):
        v += [f"## Voice {n}: {t['label']}", "", f"*{t['line']}*", "", page(t["english"]), ""]
    for n, rnd in enumerate(doc["rounds"], 1):
        t = rnd.get("take") or doc["takes"][rnd.get("voice", 0)]
        v += [f"## Note {n}", "", "\n".join(f"> {line}" for line in rnd["note"].splitlines()), "",
              f"**The house's reply:** {rnd['reply']}", ""]
        if rnd["changed"]:
            v += ["**What changed:**", ""] + [f"- {c}" for c in rnd["changed"]] + [""]
        if rnd.get("question"):
            v += [f"**The house asks:** {rnd['question']}", ""]
        v += [f"**Page 1 again, in voice {rnd.get('voice', 0)} ({t['label']}):**", "", page(rnd["english"]), ""]
    first = doc["takes"][0]["english"]
    v += ["## Page 1 in Japanese", "", "\n\n".join(ja.get(pid.split("–")[0], "") for pid, _ in first), ""]
    v += [f"The draft will be written in voice {voice} unless you approve another."]

    b = [f"# The analysis: {title}", "", context.bible(bible).split("\n", 2)[2].strip()]
    return {"reading.md": "\n".join(r) + "\n", "bible.md": "\n".join(b) + "\n", "voices.md": "\n".join(v) + "\n"}
