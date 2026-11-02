"""The editors' desk (docs/EDITORS-DESK.md): invite links, allowances in drops, and whole runs.

An invite link carries a long random token; only its salted hash is stored. The editor it names
picks an eligible work, agrees to publication, and starts a run. The whole estimate is reserved
from their allowance first; the run goes in a background thread under a cap of the reservation
plus the house's 20% margin; at the end what it spent is charged (never more than the
reservation) and the rest released. One run goes at a time, across the whole site.
"""

import json
import math
import os
import re
import secrets
import threading
from functools import lru_cache

from house import budget, events, orchestrator, works
from house.client import make_client
from house.comments import LINK, digest
from house.db import connect, dumps
from house.edition import _date

OVERRUN = 1.2  # the house covers up to 20% over the reservation (docs/EDITORS-DESK.md, "Money")
MAX_CREDIT = 60
DEFAULT_OPTIONS: dict = {}  # run options every desk run gets; tests set the recorded models here

# The stage a run is on, in words a reader understands. A run's `stage` is the last one completed,
# so the label is for the stage after it.
STAGE_LABELS = {
    "parse": "preparing the text",
    "first-read": "reading the whole story",
    "crux-check": "reading it a second time",
    "bible": "settling names, terms and voice",
    "draft": "drafting",
    "readers": "checking against the Japanese",
    "desk": "deciding what to change",
    "copy-desk": "checking the English",
    "notes": "notes",
    "release": "final read",
}
GOING = ("queued", "running")

_lock = threading.Lock()
_live: set[int] = set()  # runs with a thread in this process


class Refused(Exception):
    """A desk action that can't go ahead; the message is for the editor, `code` the HTTP status."""

    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.code = code


# --- invites -----------------------------------------------------------------------------------

def invite(conn, name: str, drops: int = 4000, work: str | None = None, reason: str = "invite") -> str:
    """A new editor with an allowance and an invite link. Returns the token: it isn't stored."""
    if work is not None:
        works.info(work)  # unknown work → KeyError
    token = secrets.token_urlsafe(32)
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
    conn.commit()
    return cur.rowcount > 0 or bool(conn.execute(f"SELECT 1 FROM invite WHERE {col}=?", (val,)).fetchone())


def _invite(conn, token: str):
    if not token:
        return None
    return conn.execute("SELECT * FROM invite WHERE token_hash=? AND revoked_at IS NULL", (digest(token),)).fetchone()


def editor(conn, token: str):
    """The person an invite token names, or None for an unknown or revoked token."""
    inv = _invite(conn, token)
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
    return math.ceil(round(budget.drops(usd), 6))


def _used(conn, run_id: int) -> int:
    """Drops a run has spent so far, from the ledger. Cached responses cost nothing."""
    return _drops(conn.execute("SELECT COALESCE(SUM(cost_usd),0) FROM call WHERE run_id=?", (run_id,)).fetchone()[0])


# --- works -------------------------------------------------------------------------------------

@lru_cache(maxsize=64)
def _chars(work_id: str, mtime: float) -> int:
    return sum(len(p.text) for p in works.parse(work_id).translatable())


# What a run really costs per sheet, before the ledger has finished runs of its own to go on:
# measured on 「晩餐」, 2 Nov 2026 (1,486 drops for 8.5 sheets). The engine's own pool, DROPS_PER_SHEET,
# is what it aims to spend; an estimate that reserves less than a run costs leaves runs stuck at the cap.
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
                rates.append(budget.drops(r["usd"]) / budget.sheets(_chars(r["work_id"], path.stat().st_mtime)))
    measured = sum(rates) / len(rates) * 1.1 if rates else FALLBACK_DROPS_PER_SHEET
    return max(budget.DROPS_PER_SHEET, measured)


def eligible_works(conn=None) -> list[dict]:
    """The works a run can start on: the rights record passes and the source is stored."""
    rate = drops_per_sheet(conn)
    out = []
    for wid, w in works.registry().items():
        path = works.source_path(wid)
        if not works.eligible(w.get("rights", {})) or not path.exists():
            continue
        chars = _chars(wid, path.stat().st_mtime)
        sheets = budget.sheets(chars)
        out.append({"id": wid, "title": w["title"], "title_en": w.get("title_en") or w["title"],
                    "author_en": w.get("author_en") or w["author"],
                    "first_published_year": w["rights"].get("first_published_year"), "blurb": w.get("blurb"),
                    "chars": chars, "sheets": sheets, "estimate": math.ceil(sheets * rate)})
    return out


# --- runs --------------------------------------------------------------------------------------

def _busy(conn) -> bool:
    return bool(conn.execute(f"SELECT 1 FROM run WHERE status IN {GOING}").fetchone())


def _credit(credit: str | None) -> str:
    credit = re.sub(r"\s+", " ", credit or "").strip()
    if len(credit) > MAX_CREDIT:
        raise Refused(f"Keep the name to {MAX_CREDIT} characters.")
    if LINK.search(credit):
        raise Refused("No links in the name.")
    return credit


def _hold(conn, run_id: int, person_id: int) -> None:
    """Reserve what's left of a run's reservation before an attempt at it."""
    options = _options(conn, run_id)
    hold = max(options["reserved_drops"] - options.get("charged_drops", 0), 0)
    if not hold:
        # It used its whole reservation and stopped at the cap: resuming holds a quarter more and
        # raises the cap to match, so what's left can finish.
        hold = math.ceil(options["reserved_drops"] / 4)
        options["reserved_drops"] += hold
        spent_usd = conn.execute("SELECT COALESCE(SUM(cost_usd),0) FROM call WHERE run_id=?", (run_id,)).fetchone()[0]
        conn.execute("UPDATE run SET cap_usd=? WHERE id=?", (spent_usd + hold * budget.DROP_USD * OVERRUN, run_id))
    left = allowance(conn, person_id)["available"]
    if hold > left:
        raise Refused(f"This needs {hold:,} drops and you have {left:,} left.")
    conn.execute("UPDATE allowance SET drops_reserved = drops_reserved + ? WHERE id=?",
                 (hold, options["allowance_id"]))
    options["held_drops"] = hold
    conn.execute("UPDATE run SET status='queued', options=? WHERE id=?", (dumps(options), run_id))


def start(db, token: str, work_id: str, agree: bool, credit: str | None) -> int:
    """Start a whole run for the editor this token names. Returns the run id; refusals raise Refused."""
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
    with _lock:
        if _busy(conn):
            raise Refused("Another run is going on the site. One runs at a time: try again when it has finished.", 409)
        estimate = work["estimate"]
        left = allowance(conn, person["id"])["available"]
        if estimate > left:
            raise Refused(f"This run needs {estimate:,} drops and you have {left:,} left.")
        info = works.info(work_id)
        conn.execute("INSERT OR IGNORE INTO work (id, aozora_id, title, author) VALUES (?,?,?,?)",
                     (work_id, info.get("aozora_id"), info["title"], info["author"]))
        conn.execute("UPDATE person SET credit_as=? WHERE id=?", (credit, person["id"]))
        cap = estimate * budget.DROP_USD * OVERRUN
        options = {"pipeline": orchestrator.PIPELINE, **DEFAULT_OPTIONS, "editor_id": person["id"],
                   "allowance_id": _allowance_row(conn, person["id"]), "reserved_drops": estimate,
                   "credit": credit or "an editor"}
        run_id = orchestrator.new_run(conn, work_id, f"desk:{person['id']}", cap, options)
        _hold(conn, run_id, person["id"])
        conn.commit()
        events.emit(conn, run_id, "house", "run.started", {"work": work_id, "options": options, "cap_usd": cap})
        _live.add(run_id)
    spawn(go, db, run_id, None)
    return run_id


def resume(db, token: str, run_id: int) -> None:
    """Carry on a run of this editor's that stopped, from the stage after the last one completed."""
    conn = connect(db)
    person = editor(conn, token)
    if not person:
        raise Refused("That invite link isn't valid.", 404)
    row = _run(conn, run_id, person["id"])
    if not row:
        raise Refused("There's no such run on this desk.", 404)
    if row["status"] == "done":
        raise Refused("That run has finished.")
    with _lock:
        if row["status"] in GOING or run_id in _live:
            raise Refused("That run is still going.", 409)
        if _busy(conn):
            raise Refused("Another run is going on the site. One runs at a time: try again when it has finished.", 409)
        nxt = _next(row["stage"])
        if nxt is None:
            raise Refused("That run has nothing left to do.")
        _hold(conn, run_id, person["id"])
        conn.commit()
        _live.add(run_id)
    spawn(go, db, run_id, nxt)


def spawn(fn, *args) -> None:
    """Run fn in a background thread. Tests replace this to run it in place."""
    threading.Thread(target=fn, args=args, daemon=True, name=f"desk-run-{args[1]}").start()


def go(db, run_id: int, from_: str | None) -> None:
    """One attempt at a desk run, in its own connection: run the stages, then settle the allowance."""
    conn = connect(db)
    try:
        row = conn.execute("SELECT * FROM run WHERE id=?", (run_id,)).fetchone()
        client = make_client(conn, run_cap=row["cap_usd"])
        conn.execute("UPDATE run SET status='running' WHERE id=?", (run_id,))
        conn.commit()
        try:
            orchestrator.run(conn, client, row["work_id"], run_id=run_id, from_=from_)
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
    i = orchestrator.NAMES.index(stage) + 1
    return orchestrator.NAMES[i] if i < len(orchestrator.NAMES) else None


# --- what the page shows -----------------------------------------------------------------------

def _run_dict(conn, row) -> dict:
    options = json.loads(row["options"] or "{}")
    status = row["status"] if row["status"] in ("queued", "running", "done", "failed", "interrupted") else "interrupted"
    if status == "done":
        label = "published"
    elif status == "queued" and row["stage"] is None:
        label = "waiting to start"
    else:
        label = STAGE_LABELS.get(_next(row["stage"]) or "release", "")
    try:
        title_en = works.info(row["work_id"]).get("title_en") or row["work_id"]
    except KeyError:
        title_en = row["work_id"]
    return {"id": row["id"], "work_id": row["work_id"], "title_en": title_en, "status": status,
            "stage": row["stage"], "stage_label": label, "reserved": options.get("reserved_drops", 0),
            "spent": min(_used(conn, row["id"]), options.get("reserved_drops", 0)),
            "started": _date(row["created_at"]), "edition_url": f"/read/{row['work_id']}" if status == "done" else None}


def runs(conn, person_id: int) -> list[dict]:
    return [_run_dict(conn, r) for r in conn.execute(
        "SELECT * FROM run WHERE json_extract(options, '$.editor_id')=? ORDER BY id DESC", (person_id,))]


def run_state(conn, token: str, run_id: int) -> dict | None:
    """One run, as `state` lists it, if it's this editor's."""
    person = editor(conn, token)
    row = _run(conn, run_id, person["id"]) if person else None
    return _run_dict(conn, row) if row else None


def state(conn, token: str) -> dict | None:
    """Everything the desk page needs, or None for an unknown or revoked token."""
    inv = _invite(conn, token)
    person = editor(conn, token)
    if not person:
        return None
    left = allowance(conn, person["id"])
    published = {r[0] for r in conn.execute("SELECT DISTINCT work_id FROM edition WHERE current_release IS NOT NULL")}
    listed = [{"id": w["id"], "title": w["title"], "title_en": w["title_en"], "author_en": w["author_en"],
               "year": w["first_published_year"], "blurb": w["blurb"], "sheets": round(w["sheets"], 1),
               "estimate": w["estimate"], "covered": w["estimate"] <= left["available"],
               "has_edition": w["id"] in published} for w in eligible_works(conn)]
    suggested = inv["suggested_work"]
    if suggested is None:  # the shortest work the allowance covers
        covered = sorted((w for w in listed if w["covered"]), key=lambda w: w["estimate"])
        suggested = covered[0]["id"] if covered else None
    return {"token": token, "editor": {"name": person["name"], "credit_as": person["credit_as"]},
            "allowance": left, "suggested": suggested, "busy": _busy(conn), "works": listed,
            "runs": runs(conn, person["id"])}
