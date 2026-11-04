"""The editors' desk (docs/EDITORS-DESK.md): invite links, allowances in drops, and whole runs.

An invite link carries a long random token; only its salted hash is stored. Opening it signs the
editor in (house/accounts.py), so the desk's functions take either the token or, from a signed-in
session, the person's id: `editor` resolves both, and everything after it is one path. The editor picks an eligible work, agrees to publication, and starts a run. The whole estimate is reserved
from their allowance first; the run goes in a background thread under a cap of the reservation
plus the house's 20% margin; at the end what it spent is charged (never more than the
reservation) and the rest released. A run pauses once, at the checkpoint after the bible, for the
editor to read the house's reading, pick a voice, leave notes and approve (docs/STEERING.md).
One run goes at a time per person, and at most CAPACITY across the site.
"""

import json
import math
import os
import re
import secrets
import threading
from functools import lru_cache

from house import accounts, acquire, budget, events, orchestrator, works
from house.client import make_client
from house.comments import LINK, digest
from house.db import connect, dumps
from house.edition import ACCENTS, _date, cast_names, plain, plain_all
from house.lang.ja import aozora

# An allowance is counted in drops of ink: one drop is DROP_USD, and a sheet is 400 characters of the original.
DROP_USD = float(os.environ.get("KEIKAKU_DROP_USD", "0.0006"))
SHEET_CHARS = 400
MIN_DROPS_PER_SHEET = 100


def drops(usd: float) -> float:
    return usd / DROP_USD


def sheets(chars: int) -> float:
    return chars / SHEET_CHARS


OVERRUN = 1.2  # the house covers up to 20% over the reservation (docs/EDITORS-DESK.md, "Money")
MAX_CREDIT = 60
DEFAULT_OPTIONS: dict = {}  # run options every desk run gets; tests set the recorded models here

# The stage a run is on, in words a reader understands. A run's `stage` is the last one completed,
# so the label is for the stage after it.
STAGE_LABELS = {  # one per stage in orchestrator.NAMES
    "parse": "preparing the text",
    "parts": "dividing the text into parts",
    "first-read": "reading the whole story",
    "crux-check": "reading it a second time",
    "bible": "settling names, terms and voice",
    "checkpoint": "waiting for the editor",
    "draft": "drafting",
    "readers": "checking against the Japanese",
    "desk": "deciding what to change",
    "final-read": "reading the finished English",
    "copy-desk": "checking the English",
    "notes": "writing the notes",
    "release": "publishing",
}
# The stages a person sees on a translation's page, in their order: a few steps, each one or more engine stages.
STEPS = [("Reading the story and writing the analysis", ("parse", "parts", "first-read", "crux-check", "bible")),
         ("Your review: edit the analysis or send notes, then approve", ("checkpoint",)),
         ("Drafting the English", ("draft",)),
         ("Checking it against the Japanese and revising", ("readers", "desk")),
         ("A last read and a copy-edit", ("final-read", "copy-desk")),
         ("Writing the notes", ("notes",)),
         ("Publishing", ("release",))]
GOING = ("queued", "running")
STATUSES = ("queued", "running", "waiting", "done", "failed", "interrupted")
CAPACITY = 3  # runs queued or running across the site at once
FULL = "Fortleben is full at the moment: three translations are going. Try again in a little while."
YOURS = "You have a translation going already. Start the next one when it has finished."
OTHER = "You have another translation going. Carry this one on when that one has finished."
NOTE_CHARS = 2000

_lock = threading.Lock()
_live: set[int] = set()  # runs with a thread in this process
_steering: set[int] = set()  # waiting runs with a note being read in this process


class Refused(Exception):
    """A desk action that can't go ahead; the message is for the editor, `code` the HTTP status."""

    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.code = code


# --- invites -----------------------------------------------------------------------------------

def invite(conn, name: str, drops: int = 4000, work: str | None = None, reason: str = "invite") -> str:
    """A new editor with an allowance and an invite link. Returns the token: it isn't stored."""
    if work is not None:
        works.info(work, conn)  # unknown work → KeyError
    token = secrets.token_hex(24)  # letters and digits only: a token can be a CLI argument and a path
    person = conn.execute("INSERT INTO person (name, trust) VALUES (?, 'editor')", (name.strip(),)).lastrowid
    conn.execute("INSERT INTO allowance (person_id, drops_granted, reason) VALUES (?,?,?)", (person, int(drops), reason))
    conn.execute("INSERT INTO invite (token_hash, person_id, suggested_work) VALUES (?,?,?)",
                 (digest(token), person, work))
    conn.commit()
    return token


def revoke(conn, token_or_id: str | int) -> bool:
    """Revoke an invite by its token or its id. False if there's no such invite."""
    key = str(token_or_id)
    col, val = ("id", int(key)) if key.isdigit() else ("token_hash", digest(key))
    cur = conn.execute(f"UPDATE invite SET revoked_at=datetime('now') WHERE {col}=? AND revoked_at IS NULL", (val,))
    # A revoked link takes the person's way in with it: their sessions, any email address and password
    # they added (so a reset can't let them back in) and any reset link already sent.
    for (pid,) in conn.execute(f"SELECT person_id FROM invite WHERE {col}=?", (val,)).fetchall():
        conn.execute("UPDATE person SET password_hash=NULL, email=NULL WHERE id=?", (pid,))
        conn.execute("DELETE FROM session WHERE person_id=?", (pid,))
        conn.execute("UPDATE reset SET used_at=datetime('now') WHERE person_id=? AND used_at IS NULL", (pid,))
    conn.commit()
    return cur.rowcount > 0 or bool(conn.execute(f"SELECT 1 FROM invite WHERE {col}=?", (val,)).fetchone())


def _invite(conn, token: str):
    if not token:
        return None
    return conn.execute("SELECT * FROM invite WHERE token_hash=? AND revoked_at IS NULL", (digest(token),)).fetchone()


Who = str | int  # an invite token, or the id of a signed-in person


def editor(conn, who: Who):
    """The person an invite token or a signed-in person's id names, or None for an unknown or revoked token."""
    if isinstance(who, int):
        return conn.execute("SELECT * FROM person WHERE id=?", (who,)).fetchone()
    inv = _invite(conn, who)
    if not inv:
        return None
    conn.execute("UPDATE invite SET last_used_at=datetime('now') WHERE id=?", (inv["id"],))
    conn.commit()
    return conn.execute("SELECT * FROM person WHERE id=?", (inv["person_id"],)).fetchone()


def invites(conn) -> list[dict]:
    """Every invite, for the command line: never the hash."""
    return [{"id": r["id"], "name": r["name"], "left": allowance(conn, r["person_id"])["available"],
             "created": r["created_at"], "revoked": r["revoked_at"], "last_used": r["last_used_at"]}
            for r in conn.execute("SELECT i.*, p.name FROM invite i JOIN person p ON p.id = i.person_id ORDER BY i.id")]


# --- allowance ---------------------------------------------------------------------------------

def allowance(conn, person_id: int) -> dict:
    g, r, s = conn.execute("SELECT COALESCE(SUM(drops_granted),0), COALESCE(SUM(drops_reserved),0), "
                           "COALESCE(SUM(drops_spent),0) FROM allowance WHERE person_id=?", (person_id,)).fetchone()
    return {"granted": g, "reserved": r, "spent": s, "available": g - r - s}


def _allowance_row(conn, person_id: int) -> int:
    """Reservations and spending go on the person's first allowance row; totals are summed."""
    return conn.execute("SELECT id FROM allowance WHERE person_id=? ORDER BY id LIMIT 1", (person_id,)).fetchone()["id"]


def _drops(usd: float) -> int:
    return math.ceil(round(drops(usd), 6))


def _used(conn, run_id: int) -> int:
    """Drops a run has spent so far, from the ledger. Cached responses cost nothing."""
    return _drops(conn.execute("SELECT COALESCE(SUM(cost_usd),0) FROM call WHERE run_id=?", (run_id,)).fetchone()[0])


# --- works -------------------------------------------------------------------------------------

@lru_cache(maxsize=256)
def _chars(work_id: str, mtime: float) -> int:
    """Characters to translate, from the stored text (the parse needs no record, so no connection)."""
    text = works.source_path(work_id).read_text(encoding="utf-8")
    return sum(len(p.text) for p in aozora.parse(text).translatable())


# What a run really costs per sheet, before the ledger has finished runs of its own to go on:
# measured on 「晩餐」, 2 Nov 2026 (1,486 drops for 8.5 sheets). An estimate that reserves less than a run costs leaves runs stuck at the cap.
FALLBACK_DROPS_PER_SHEET = int(os.environ.get("DESK_DROPS_PER_SHEET", 175))


def drops_per_sheet(conn=None) -> float:
    """The rate estimates use: the average cost per sheet of the last finished runs in the ledger, as
    first made (so a run served from the cache still counts at its real price), with a tenth on top."""
    rates = []
    if conn is not None:
        for r in conn.execute("SELECT r.id, r.work_id, SUM(c.list_cost_usd) AS usd FROM run r JOIN call c ON c.run_id = r.id "
                              "WHERE r.status='done' GROUP BY r.id ORDER BY r.id DESC LIMIT 5"):
            path = works.source_path(r["work_id"])
            if path.exists() and r["usd"]:
                rates.append(drops(r["usd"]) / sheets(_chars(r["work_id"], path.stat().st_mtime)))
    measured = sum(rates) / len(rates) * 1.1 if rates else FALLBACK_DROPS_PER_SHEET
    return max(MIN_DROPS_PER_SHEET, measured)


def eligible_works(conn=None) -> list[dict]:
    """The works a run can start on: the rights record passes and the source is stored. With a
    connection, the works added from Aozora links too, after the repo's own."""
    rate = drops_per_sheet(conn)
    out = []
    for wid, w in works.registry(conn).items():
        path = works.source_path(wid)
        if not works.eligible(w.get("rights", {})) or not path.exists():
            continue
        chars = _chars(wid, path.stat().st_mtime)
        n = sheets(chars)
        # No English title is "" (a work card that failed, or an old one that copied the Japanese)
        title_en = w.get("title_en") if w.get("title_en") != w["title"] else None
        author_en = w.get("author_en") if w.get("author_en") != w["author"] else None
        out.append({"id": wid, "title": w["title"], "title_en": title_en or "", "author": w["author"],
                    "author_en": author_en or "",
                    "first_published_year": w["rights"].get("first_published_year"), "blurb": w.get("blurb"),
                    "chars": chars, "sheets": n, "estimate": math.ceil(n * rate), "added": bool(w.get("added"))})
    return out


ADDS_PER_DAY = 10  # links one person may have read from Aozora in a day, so nobody mirrors it through the site
TOO_MANY_ADDS = "You've added ten works from Aozora today. Add more tomorrow."


def add_work(db, token: Who, url: str) -> dict:
    """Add a work from an Aozora link for the editor this token names (house/acquire.py). Returns its
    row as the desk lists it; refusals raise Refused. A link to a work already here costs nothing."""
    conn = connect(db)
    person = editor(conn, token)
    if not person:
        raise Refused("That invite link isn't valid.", 404)
    url = (url or "").strip()
    if not url:
        raise Refused("Paste a link first.")
    try:
        _, _, card_url = acquire.aozora_card.card(url)
    except acquire.NotAWork as e:
        raise Refused(str(e)) from None
    if (not acquire.find(conn, card_url) and not acquire.refused_before(conn, card_url)
            and acquire.adds_today(conn, person["id"]) >= ADDS_PER_DAY):
        raise Refused(TOO_MANY_ADDS, 429)
    try:
        work_id, _ = acquire.add(conn, url, person["id"])
    except acquire.Refused as e:
        raise Refused(str(e)) from None
    row = next((w for w in _listed(conn, person) if w["id"] == work_id), None)
    if not row:  # a work in the repo's list whose text isn't stored here
        raise Refused("That work isn't one a run can start on.")
    return row


# --- runs --------------------------------------------------------------------------------------

def _full(conn, but: int | None = None) -> bool:
    """The house has no room: CAPACITY runs are queued or running, from the desk or anywhere else."""
    return conn.execute(f"SELECT COUNT(*) FROM run WHERE status IN {GOING} AND id IS NOT ?",
                        (but,)).fetchone()[0] >= CAPACITY


def _going(conn, person_id: int, but: int | None = None) -> bool:
    """This person has a run queued or running. A run waiting at the checkpoint doesn't count."""
    return bool(conn.execute(f"SELECT 1 FROM run WHERE status IN {GOING} AND json_extract(options, '$.editor_id')=? "
                             "AND id IS NOT ?", (person_id, but)).fetchone())


def _room(conn, person_id: int, but: int | None = None) -> None:
    if _going(conn, person_id, but):
        raise Refused(YOURS if but is None else OTHER, 409)
    if _full(conn, but):
        raise Refused(FULL, 409)


RESERVED = {"the house", "house", "keikaku", "fortleben", "an editor"}  # names the site gives its own editions


def _credit(credit: str | None) -> str:
    credit = re.sub(r"\s+", " ", credit or "").strip()
    if len(credit) > MAX_CREDIT:
        raise Refused(f"Keep the name to {MAX_CREDIT} characters.")
    if LINK.search(credit):
        raise Refused("No links in the name.")
    if credit.casefold() in RESERVED:
        raise Refused("That name is the site's own. Use yours.")
    return credit


NO_KEY = "This desk has no key any more. Add a new key on your desk to translate."


def _signed_up(conn, person_id: int) -> bool:
    """The person came in through /signup with their own key, not an invite with an allowance."""
    return not conn.execute("SELECT 1 FROM allowance WHERE person_id=?", (person_id,)).fetchone()


def _can_hold(conn, run_id: int, person_id: int) -> None:
    """Refused, without changing anything, if _hold would refuse: a run on a key that's gone, or an
    allowance that doesn't cover what's left of the reservation (or a quarter more if none is)."""
    options = _options(conn, run_id)
    if options.get("own_key"):
        if not accounts.key_for(conn, person_id):
            raise Refused(NO_KEY)
        return
    need = (max(options["reserved_drops"] - options.get("charged_drops", 0), 0)
            or math.ceil(options["reserved_drops"] / 4))
    left = allowance(conn, person_id)["available"]
    if need > left:
        raise Refused(f"This needs {need:,} drops and you have {left:,} left.")


def _hold(conn, run_id: int, person_id: int) -> None:
    """Reserve what's left of a run's reservation before an attempt at it. A run on the editor's own
    key holds nothing: it is capped by the run cap only."""
    options = _options(conn, run_id)
    if options.get("own_key"):
        if not accounts.key_for(conn, person_id):
            raise Refused(NO_KEY)
        # A run that stopped at its cap gets another run cap's worth on their key, so it can finish.
        spent_usd = conn.execute("SELECT COALESCE(SUM(cost_usd),0) FROM call WHERE run_id=?", (run_id,)).fetchone()[0]
        conn.execute("UPDATE run SET status='queued', cap_usd=MAX(cap_usd, ?) WHERE id=?",
                     (spent_usd + budget.Budget(conn).run_cap, run_id))
        return
    hold = max(options["reserved_drops"] - options.get("charged_drops", 0), 0)
    if not hold:
        # It used its whole reservation and stopped at the cap: resuming holds a quarter more and
        # raises the cap to match, so what's left can finish.
        hold = math.ceil(options["reserved_drops"] / 4)
        options["reserved_drops"] += hold
        spent_usd = conn.execute("SELECT COALESCE(SUM(cost_usd),0) FROM call WHERE run_id=?", (run_id,)).fetchone()[0]
        conn.execute("UPDATE run SET cap_usd=? WHERE id=?", (spent_usd + hold * DROP_USD * OVERRUN, run_id))
    left = allowance(conn, person_id)["available"]
    if hold > left:
        raise Refused(f"This needs {hold:,} drops and you have {left:,} left.")
    conn.execute("UPDATE allowance SET drops_reserved = drops_reserved + ? WHERE id=?",
                 (hold, options["allowance_id"]))
    options["held_drops"] = hold
    conn.execute("UPDATE run SET status='queued', options=? WHERE id=?", (dumps(options), run_id))


# The estimate is worked out afresh at start from the latest finished runs, so it can move after the
# page was drawn. Starting never holds more than the page showed; if the page showed far less, it's out of date.
STALE_ESTIMATE = 0.75
ESTIMATE_CHANGED = "The estimate for this work has changed since the page loaded. Reload the page to see the new one."


def start(db, token: Who, work_id: str, agree: bool, credit: str | None, checkpoint: bool = True,
          shown: int | None = None, accent: str | None = None) -> int:
    """Start a whole run for the editor this token names. Returns the run id; refusals raise Refused.
    The run pauses at the checkpoint unless `checkpoint` is False. `shown` is the estimate the desk
    page showed: the run holds the smaller of it and the fresh one, or is refused if it's well below."""
    conn = connect(db)
    person = editor(conn, token)
    if not person:
        raise Refused("That invite link isn't valid.", 404)
    if not agree:
        raise Refused("Agree to publication first: everything run here is published here.")
    work = {w["id"]: w for w in eligible_works(conn)}.get(work_id)
    if not work:
        raise Refused("That work isn't one a run can start on.")
    credit = _credit(credit)
    if accent is not None and accent not in ACCENTS:
        raise Refused("Pick one of the colours shown.")
    with _lock:
        _room(conn, person["id"])
        estimate = work["estimate"]
        own = accounts.has_key(person)
        if shown is not None and not own:
            if shown < estimate * STALE_ESTIMATE:
                raise Refused(ESTIMATE_CHANGED, 409)
            estimate = min(shown, estimate)
        if not own and _signed_up(conn, person["id"]):
            raise Refused(NO_KEY)
        if own and estimate * DROP_USD > budget.Budget(conn).run_cap:
            raise Refused("That work is longer than one run here may spend. Pick a shorter one.")
        left = allowance(conn, person["id"])["available"]
        if not own and estimate > left:
            raise Refused(f"This run needs {estimate:,} drops and you have {left:,} left.")
        info = works.info(work_id, conn)
        conn.execute("INSERT OR IGNORE INTO work (id, aozora_id, title, author) VALUES (?,?,?,?)",
                     (work_id, info.get("aozora_id"), info["title"], info["author"]))
        conn.execute("UPDATE person SET credit_as=? WHERE id=?", (credit, person["id"]))
        cap = budget.Budget(conn).run_cap if own else estimate * DROP_USD * OVERRUN
        options = {"pipeline": orchestrator.PIPELINE, **DEFAULT_OPTIONS, "editor_id": person["id"],
                   **({"own_key": True} if own else
                      {"allowance_id": _allowance_row(conn, person["id"]), "reserved_drops": estimate}),
                   "credit": credit or "an editor", "checkpoint": bool(checkpoint),
                   **({"accent": accent} if accent else {})}
        run_id = orchestrator.new_run(conn, work_id, f"desk:{person['id']}", cap, options)
        _hold(conn, run_id, person["id"])
        conn.commit()
        events.emit(conn, run_id, "house", "run.started", {"work": work_id, "options": options, "cap_usd": cap})
        _live.add(run_id)
    spawn(go, db, run_id, None)
    return run_id


def _mine(conn, token: Who, run_id: int):
    person = editor(conn, token)
    if not person:
        raise Refused("That invite link isn't valid.", 404)
    row = _run(conn, run_id, person["id"])
    if not row:
        raise Refused("There's no such run on this desk.", 404)
    return person, row


def resume(db, token: Who, run_id: int) -> None:
    """Carry on a run of this editor's that stopped, from the stage after the last one completed.
    A run that stopped after it was approved at the checkpoint carries on from the draft; a run
    waiting at the checkpoint goes on only through approve()."""
    conn = connect(db)
    person, row = _mine(conn, token, run_id)
    if row["status"] == "done":
        raise Refused("That run has finished.")
    if row["status"] == "waiting":
        raise Refused("That run is waiting for you: pick a voice and approve it to carry on.", 409)
    if not resumable(json.loads(row["options"] or "{}")):
        raise Refused("Your key was turned down, so this run can't go on. Start it afresh with a key that works.", 409)
    with _lock:
        # Queued but with no thread is a run approved at the checkpoint whose attempt never began.
        approved = row["status"] == "queued" and row["stage"] == "checkpoint"
        if run_id in _live or (row["status"] in GOING and not approved):
            raise Refused("That run is still going.", 409)
        _room(conn, person["id"], but=run_id)
        nxt = _next(row["stage"])
        if nxt is None:
            raise Refused("That run has nothing left to do.")
        _hold(conn, run_id, person["id"])
        conn.commit()
        _live.add(run_id)
    spawn(go, db, run_id, nxt)


# --- the checkpoint ----------------------------------------------------------------------------
# The engine side is house/steer.py (docs/STEERING.md, "The contract between lanes"). It's imported
# when it's used, through these two names, which tests replace.

def steer_round(conn, client, run_id: int, note: str) -> dict:
    from house import steer
    return steer.steer(conn, client, run_id, note)


def approve_run(conn, run_id: int, voice: int) -> None:
    from house import steer
    steer.approve(conn, run_id, voice)


def _note(note: str | None) -> str:
    note = (note or "").strip()
    if not note:
        raise Refused("Write a note first.")
    if len(note) > NOTE_CHARS:
        raise Refused(f"Keep a note to {NOTE_CHARS:,} characters.")
    return note


def _voice(conn, row, voice) -> int:
    takes = _checkpoint_doc(conn, row["id"]).get("takes") or []
    if isinstance(voice, bool) or not isinstance(voice, int) or not 0 <= voice < len(takes):
        raise Refused("Pick one of the voices.")
    return voice


def _set_voice(conn, run_id: int, voice: int) -> None:
    options = _options(conn, run_id)
    if options.get("voice") != voice:
        options["voice"] = voice
        conn.execute("UPDATE run SET options=? WHERE id=?", (dumps(options), run_id))


def steer(db, token: Who, run_id: int, note: str | None, voice=None) -> None:
    """Send the house a note on a run waiting at the checkpoint. The house reads it in the background;
    the round lands in the checkpoint document. `voice`, if given, is the take the person has picked,
    so page 1 comes back in that voice."""
    conn = connect(db)
    person, row = _mine(conn, token, run_id)
    note = _note(note)
    if _options(conn, run_id).get("own_key") and not accounts.key_for(conn, person["id"]):
        raise Refused(NO_KEY)  # the note would be read with no key, and fail
    with _lock:
        if row["status"] != "waiting":
            raise Refused("Notes go in while the run is waiting at the checkpoint, before the draft starts. This one isn't.", 409)
        if run_id in _steering:
            raise Refused("keikaku is still reading your last note.", 409)
        if voice is not None:
            voice = _voice(conn, row, voice)  # checked now; it's kept only once the note is read
        options = _options(conn, run_id)
        options.pop("steer_error", None)
        conn.execute("UPDATE run SET options=? WHERE id=?", (dumps(options), run_id))
        conn.commit()
        _steering.add(run_id)
    spawn(read_note, db, run_id, note, voice)


def read_note(db, run_id: int, note: str, voice: int | None = None) -> None:
    """One round of steering, in its own connection, in the voice picked with the note (the round
    redrafts page 1 in it). A failure is kept for the page to show, and leaves the voice as it was."""
    conn = connect(db)
    try:
        row = conn.execute("SELECT * FROM run WHERE id=?", (run_id,)).fetchone()
        before = _options(conn, run_id).get("voice")
        try:
            if voice is not None:
                _set_voice(conn, run_id, voice)
                conn.commit()
            client = make_client(conn, run_cap=row["cap_usd"], **accounts.client_key(conn, row))
            steer_round(conn, client, run_id, note)
        except Exception as e:
            conn.rollback()
            options = _options(conn, run_id)
            if before is None:
                options.pop("voice", None)
            else:
                options["voice"] = before
            options["steer_error"] = f"{type(e).__name__}: {e}"[:500]
            conn.execute("UPDATE run SET options=? WHERE id=?", (dumps(options), run_id))
            conn.commit()
        if "editor_id" in _options(conn, run_id):
            settle(conn, run_id)  # a round's few calls are charged like the rest of the run
    finally:
        _steering.discard(run_id)


def approve(db, token: Who, run_id: int, voice) -> None:
    """Approve a run waiting at the checkpoint in the voice picked, and carry it on from the draft."""
    conn = connect(db)
    person, row = _mine(conn, token, run_id)
    with _lock:
        if row["status"] != "waiting":
            raise Refused("Only a run waiting at the checkpoint can be approved. This one isn't.", 409)
        if run_id in _live:
            raise Refused("That run is still finishing its checkpoint. Try again in a moment.", 409)
        if run_id in _steering:
            raise Refused("keikaku is still reading your last note. Approve once its reply is here.", 409)
        voice = _voice(conn, row, voice)
        _room(conn, person["id"], but=run_id)
        _can_hold(conn, run_id, person["id"])  # before approving, so a refusal leaves the run waiting
        approve_run(conn, run_id, voice)
        _hold(conn, run_id, person["id"])
        conn.commit()
        _live.add(run_id)
    spawn(go, db, run_id, "draft")


FILE_CHARS = 60_000  # far more than any reading or bible the house writes
FILE_NAMES = {"reading": "The reading", "voices": "The voices", "bible": "The analysis"}


def edit_file(db, token: Who, run_id: int, name: str, text) -> bool:
    """The editor's own version of one of the files a waiting run drafts from (house/steer.py, `edit`):
    every later stage reads it, and the edition publishes what they changed. False if nothing changed."""
    from house import steer
    conn = connect(db)
    person, row = _mine(conn, token, run_id)
    if name not in FILE_NAMES:
        raise Refused("There's no such file.", 404)
    if not isinstance(text, str) or not text.strip():
        raise Refused("The file is empty. Write something in it, or leave it as it was.")
    if len(text) > FILE_CHARS:
        raise Refused(f"Keep a file to {FILE_CHARS:,} characters.")
    with _lock:
        if row["status"] != "waiting":
            raise Refused("The files can be edited only while the run waits for you, before the draft starts.", 409)
        if run_id in _steering:
            raise Refused("keikaku is still reading your last note. Edit once its reply is here.", 409)
        if run_id in _live:
            raise Refused("That run is still finishing its checkpoint. Try again in a moment.", 409)
        try:
            # named as the edition credits them, since that's where the record is published
            return steer.edit(conn, run_id, name, text, _options(conn, run_id).get("credit") or person["name"], person["id"])
        except (steer.NotWaiting, ValueError) as e:
            raise Refused(f"Not saved: {e}.")


def spawn(fn, *args) -> None:
    """Run fn in a background thread. Tests replace this to run it in place."""
    threading.Thread(target=fn, args=args, daemon=True, name=f"desk-run-{args[1]}").start()


def go(db, run_id: int, from_: str | None) -> None:
    """One attempt at a desk run, in its own connection: run the stages, then settle the allowance."""
    conn = connect(db)
    try:
        row = conn.execute("SELECT * FROM run WHERE id=?", (run_id,)).fetchone()
        client = make_client(conn, run_cap=row["cap_usd"], **accounts.client_key(conn, row))
        conn.execute("UPDATE run SET status='running' WHERE id=?", (run_id,))
        conn.commit()
        try:
            orchestrator.run(conn, client, row["work_id"], run_id=run_id, from_=from_)
            options = _options(conn, run_id)
            if options.pop("error", None):  # an earlier attempt's failure, now made good
                conn.execute("UPDATE run SET options=? WHERE id=?", (dumps(options), run_id))
                conn.commit()
        except Exception as e:  # a failed stage or a cap: the orchestrator has recorded which
            conn.rollback()
            conn.execute("UPDATE run SET status='failed' WHERE id=?", (run_id,))
            options = _options(conn, run_id)
            options["error"] = f"{type(e).__name__}: {e}"[:500]
            conn.execute("UPDATE run SET options=? WHERE id=?", (dumps(options), run_id))
            conn.commit()
        settle(conn, run_id)
    finally:
        _live.discard(run_id)


def settle(conn, run_id: int) -> None:
    """Charge what the run spent, up to its reservation (an overrun is the house's), and release the hold."""
    options = _options(conn, run_id)
    if options.get("own_key"):
        return
    held, charged = options.get("held_drops", 0), options.get("charged_drops", 0)
    charge = max(min(_used(conn, run_id), options["reserved_drops"]) - charged, 0)
    conn.execute("UPDATE allowance SET drops_reserved = MAX(drops_reserved - ?, 0), drops_spent = drops_spent + ? "
                 "WHERE id=?", (held, charge, options["allowance_id"]))
    options.update(held_drops=0, charged_drops=charged + charge)
    conn.execute("UPDATE run SET options=? WHERE id=?", (dumps(options), run_id))
    conn.commit()


def recover(conn) -> list[int]:
    """At startup: a run left going with no thread behind it was interrupted. Desk runs are settled,
    so their hold is released until the editor resumes them."""
    # Only desk runs: a run started from the command line on the same database may still be going.
    stuck = [r["id"] for r in conn.execute(f"SELECT id FROM run WHERE status IN {GOING} AND label LIKE 'desk:%'")
             if r["id"] not in _live]
    for run_id in stuck:
        conn.execute("UPDATE run SET status='interrupted' WHERE id=?", (run_id,))
        conn.commit()
        if "editor_id" in _options(conn, run_id):
            settle(conn, run_id)
    return stuck


def _options(conn, run_id: int) -> dict:
    return json.loads(conn.execute("SELECT options FROM run WHERE id=?", (run_id,)).fetchone()["options"] or "{}")


def _run(conn, run_id: int, person_id: int):
    return conn.execute("SELECT * FROM run WHERE id=? AND json_extract(options, '$.editor_id')=?",
                        (run_id, person_id)).fetchone()


def _next(stage: str | None) -> str | None:
    if stage is None:
        return orchestrator.NAMES[0]
    if stage not in orchestrator.NAMES:  # an engine without the checkpoint stage
        return "draft" if stage == "checkpoint" else None
    i = orchestrator.NAMES.index(stage) + 1
    return orchestrator.NAMES[i] if i < len(orchestrator.NAMES) else None


# --- what the page shows -----------------------------------------------------------------------

def _turned_down(error: str | None) -> bool:
    e = (error or "").lower()
    return any(k in e for k in ("authenticationerror", "permissiondeniederror", "invalid api key",
                                "error code: 401", "error code: 403"))


def resumable(options: dict) -> bool:
    """A run on someone's own key that the key turned down can't go on: the key can't change part-way."""
    return not (options.get("own_key") and _turned_down(options.get("error")))


def failure(error: str | None, own_key: bool = False) -> str:
    """What stopped a run, in plain words, from the error the desk kept. Never an amount. A run on
    someone's own key can't take a different key, so a key turned down means signing up again."""
    e = (error or "").lower()
    then = "resume it and it carries on from there."
    if "capexceeded" in e or "budget ran out" in e:
        why = "It stopped when its budget ran out."
    elif any(k in e for k in ("insufficient_quota", "insufficient funds", "insufficient credit", "billing",
                              "error code: 402")):
        why, then = "It stopped when the key ran out of credit.", "top the key up, then " + then
    elif _turned_down(error):
        if own_key:
            return ("It stopped because your key was turned down. A translation can't change keys part-way, "
                    "so sign up again with a key that works and start it afresh.")
        why, then = "It stopped because the site's model key was turned down.", "once the key works again, " + then
    elif "houseclosed" in e:
        why = "It stopped because new work was switched off on the site."
    else:
        why = "It stopped on an error."
    return f"{why} Everything it finished is kept; {then}"


def steps(row, options: dict) -> list[dict]:
    """The run's STEPS, each done, now, next, or stopped (where a failed or interrupted run is). The review step is
    the editor's, and shown only for a run that stops for it."""
    names = [n for n in orchestrator.NAMES if n != "checkpoint" or options.get("checkpoint")]
    status = row["status"]
    if status == "done":
        at = len(names)
    elif status == "waiting" and "checkpoint" in names:
        at = names.index("checkpoint")
    else:
        nxt = _next(row["stage"])
        while nxt is not None and nxt not in names:  # a stage this run skips
            nxt = _next(nxt)
        at = names.index(nxt) if nxt else len(names)
    out = []
    for label, group in STEPS:
        where = [names.index(g) for g in group if g in names]
        if not where:
            continue
        state = "done" if max(where) < at else "next" if min(where) > at else "now"
        if state == "now" and status in ("failed", "interrupted"):
            state = "stopped"
        out.append({"label": label, "state": state, "yours": group == ("checkpoint",)})
    return out


def _run_dict(conn, row) -> dict:
    options = json.loads(row["options"] or "{}")
    status = row["status"] if row["status"] in STATUSES else "interrupted"
    nxt = _next(row["stage"])
    if status == "done":
        label = "published"
    elif status == "waiting":
        label = STAGE_LABELS["checkpoint"]
    elif status == "queued" and row["stage"] is None:
        label = "waiting to start"
    elif nxt == "checkpoint":
        label = "drafting the first page in each voice"
    else:
        label = STAGE_LABELS.get(nxt or "release", "")
    try:
        info = works.info(row["work_id"], conn)
        title_en = info.get("title_en") or info.get("title") or row["work_id"]
    except KeyError:
        title_en = row["work_id"]
    return {"id": row["id"], "work_id": row["work_id"], "title_en": title_en, "status": status,
            "stage": row["stage"], "stage_label": label, "reserved": options.get("reserved_drops", 0),
            "held": options.get("held_drops", 0),
            "spent": min(_used(conn, row["id"]), options.get("reserved_drops", 0)),
            "started": _date(row["created_at"]), "edition_url": _edition_url(conn, row) if status == "done" else None,
            "edit_url": _edit_url(conn, row) if status == "done" else None,
            "failure": failure(options.get("error"), bool(options.get("own_key"))) if status == "failed" else None,
            "resumable": status in ("interrupted", "failed") and resumable(options),
            "rounds": len(_checkpoint_doc(conn, row["id"]).get("rounds") or []) if status == "waiting" else 0,
            "steering": row["id"] in _steering,
            "steer_error": _steer_error(options),
            "spent_words": accounts.spent_words(conn, row["id"]) if options.get("own_key") else None,
            "steps": steps(row, options)}


def _steer_error(options: dict) -> str | None:
    error = options.get("steer_error")
    if not error:
        return None
    if _turned_down(error):
        whose = "your key" if options.get("own_key") else "the site's model key"
        return f"keikaku couldn't read that note: {whose} was turned down."
    return "keikaku couldn't read that note. Try sending it again."


def _edition_url(conn, row) -> str:
    """The edition this run released: the editor's own, beside the house's."""
    r = conn.execute("SELECT edition_id FROM release WHERE run_id=? ORDER BY id DESC LIMIT 1", (row["id"],)).fetchone()
    return f"/read/{row['work_id']}" + (f"?edition={r['edition_id']}" if r else "")


def _edit_url(conn, row) -> str | None:
    """The edition this run released, open for its editor to edit the English."""
    r = conn.execute("SELECT edition_id FROM release WHERE run_id=? ORDER BY id DESC LIMIT 1", (row["id"],)).fetchone()
    return f"/read/{row['work_id']}?edition={r['edition_id']}&edit=1" if r else None


def runs(conn, person_id: int) -> list[dict]:
    return [_run_dict(conn, r) for r in conn.execute(
        "SELECT * FROM run WHERE json_extract(options, '$.editor_id')=? ORDER BY id DESC", (person_id,))]


def run_state(conn, token: Who, run_id: int) -> dict | None:
    """One run, as `state` lists it, if it's this editor's."""
    person = editor(conn, token)
    row = _run(conn, run_id, person["id"]) if person else None
    return _run_dict(conn, row) if row else None


def _listed(conn, person) -> list[dict]:
    """The works as the desk lists them for this person: estimate, whether it's covered, whether it's on the shelf."""
    left = allowance(conn, person["id"])
    keyless = not accounts.has_key(person) and _signed_up(conn, person["id"])
    cap = budget.Budget(conn).run_cap if accounts.has_key(person) or keyless else None
    published = {r[0] for r in conn.execute("SELECT DISTINCT work_id FROM edition WHERE current_release IS NOT NULL")}
    return [{"id": w["id"], "title": w["title"], "title_en": w["title_en"], "author": w["author"], "author_en": w["author_en"],
             "year": w["first_published_year"], "blurb": w["blurb"], "sheets": round(w["sheets"], 1),
             "estimate": w["estimate"],
             "covered": w["estimate"] * DROP_USD <= cap if cap else w["estimate"] <= left["available"],
             "has_edition": w["id"] in published, "added": w["added"]} for w in eligible_works(conn)]


def state(conn, who: Who) -> dict | None:
    """Everything the desk page needs, or None for an unknown or revoked token. `base` is where the
    page's own requests go: /desk/<token> from an invite link, /desk when signed in."""
    person = editor(conn, who)
    if not person:
        return None
    inv = (_invite(conn, who) if isinstance(who, str) else conn.execute(
        "SELECT * FROM invite WHERE person_id=? AND revoked_at IS NULL ORDER BY id DESC LIMIT 1", (who,)).fetchone())
    left = allowance(conn, person["id"])
    keyless = not accounts.has_key(person) and _signed_up(conn, person["id"])  # signed up, then forgot the key
    listed = _listed(conn, person)
    suggested = inv["suggested_work"] if inv else None
    if suggested is None:  # the shortest work the allowance covers, from the repo's list before added ones
        covered = sorted((w for w in listed if w["covered"]), key=lambda w: (w["added"], w["estimate"]))
        suggested = covered[0]["id"] if covered else None
    return {"base": f"/desk/{who}" if isinstance(who, str) else "/desk", "email": person["email"],
            "has_password": bool(person["password_hash"]),
            "editor": {"name": person["name"], "credit_as": person["credit_as"]},
            "allowance": left, "suggested": suggested, "busy": _full(conn), "going": _going(conn, person["id"]),
            "works": listed, "runs": runs(conn, person["id"]), "key_tail": person["key_tail"], "keyless": keyless,
            "checkpoints": [checkpoint(conn, r) for r in conn.execute(
                "SELECT * FROM run WHERE json_extract(options, '$.editor_id')=? AND status='waiting' ORDER BY id DESC",
                (person["id"],))]}


# --- the checkpoint, for a person --------------------------------------------------------------

def _doc(conn, row, kind: str) -> dict | None:
    """The latest version of the run's reading or bible (house/stages.latest_document)."""
    from house.stages import latest_document
    return latest_document(conn, row["work_id"], kind, row["id"])


def _checkpoint_doc(conn, run_id: int) -> dict:
    """This run's checkpoint document (another run of the same work has its own), or {}."""
    from house.stages import checkpoint as stage
    return stage.document(conn, run_id)[0] or {}


def _paras(english) -> list[str]:
    return [e for _, e in (english or [])]


def checkpoint(conn, row) -> dict:
    """A run waiting at the checkpoint, shaped for the desk page: the three files every later stage reads
    (house/steer.py), the voices with page 1 under each, and the rounds of notes so far."""
    options = json.loads(row["options"] or "{}")
    cp = _checkpoint_doc(conn, row["id"])
    reading = _doc(conn, row, "reading") or {}
    bible = _doc(conn, row, "bible") or {}
    takes = cp.get("takes") or []
    cast = cast_names(bible)
    rounds = [{"note": r.get("note", ""), "reply": plain(r.get("reply", ""), cast), "changed": plain_all(r.get("changed") or [], cast),
               "question": plain(r.get("question"), cast), "english": _paras(r.get("english")), "voice": r.get("voice", 0)}
              for r in cp.get("rounds") or []]
    voice = options.get("voice", 0)
    voice = voice if isinstance(voice, int) and 0 <= voice < len(takes) else 0
    named = reading.get("voice_takes") or []
    named = named if len(named) == len(takes) else takes  # the reading's names, which a note or a hand edit may change
    voices = [{"label": plain(n.get("label", ""), cast), "line": plain(n.get("line", ""), cast), "english": _paras(t.get("english")),
               "redrafted": False} for n, t in zip(named, takes)]
    for r in rounds:  # each voice shows its latest redraft, if a note has redrafted it
        if isinstance(r["voice"], int) and 0 <= r["voice"] < len(voices):
            voices[r["voice"]].update(english=r["english"], redrafted=True)
    run = _run_dict(conn, row)
    from house import steer
    try:
        texts = steer.texts(reading, bible)
    except (KeyError, TypeError):  # a reading or bible missing its parts can't be written out as a file
        texts = {}
    edited = {"reading": bool(reading.get("edited_text")), "bible": bool(bible.get("edited_text")),
              "voices": any(e["file"] == "voices" for e in steer.edits(conn, row["id"]))}
    files = [{"name": k, "title": t, "text": texts[k], "edited": edited[k]} for k, t in FILE_NAMES.items() if k in texts]
    return {
        "run_id": row["id"], "title_en": run["title_en"], "voice": voice, "voices": voices, "rounds": rounds, "files": files,
        "steering": run["steering"], "steer_error": run["steer_error"],
    }
