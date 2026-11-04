"""The keikaku command line."""

import argparse
import sys

from house import works
from house.db import connect


def cmd_fetch(args) -> int:
    for wid in args.works or list(works.registry()):
        print(wid, works.fetch(wid))
    return 0


def cmd_add(args) -> int:
    from dotenv import load_dotenv

    from house import acquire, desk
    from house.db import ROOT

    load_dotenv(ROOT / ".env")  # the English title and blurb come from one small call on the site's key
    conn = connect(args.db)
    try:
        work_id, new = acquire.add(conn, args.url)
    except acquire.Refused as e:
        print(f"Not added: {e}")
        return 1
    w = next((w for w in desk.eligible_works(conn) if w["id"] == work_id), None)
    if not w:
        print(f"{work_id}: known, but its text isn't stored here; `keikaku fetch {work_id}` fetches it.")
        return 1
    print(f"{work_id}" + ("" if new else " (already here)") + f": {w['title']} ({w['title_en']}), {w['author_en']}, "
          f"first published {w['first_published_year']}. {w['chars']:,} characters, {w['sheets']:.1f} sheets, "
          f"about {w['estimate']:,} drops. Run it with `keikaku run {work_id}`.")
    return 0


def cmd_wish(args) -> int:
    """Put a work on the public wishlist (adding it from Aozora first, as `add` does), set how many asked
    for it, give it a summary, or take it off with --count 0. With no link, print the list."""
    from dotenv import load_dotenv

    from house import acquire, wishlist
    from house.db import ROOT

    load_dotenv(ROOT / ".env")
    conn = connect(args.db)
    if not args.url:
        lists = wishlist.entries(conn)
        for w in lists["wanted"] + lists["translated"]:
            print(f"{w['count']:>3}  {w['id']}: {w['title']} ({w['title_en']}), {w['author_en']}, {w['year']}, "
                  f"{w['sheets']:g} sheets{', translated' if w['edition_url'] else ''}\n     {w['blurb'] or ''}")
        return 0
    try:
        work_id, _ = acquire.add(conn, args.url)
    except acquire.Refused as e:
        print(f"Not added: {e}")
        return 1
    if args.summary is not None:
        conn.execute("UPDATE work SET blurb=? WHERE id=?", (args.summary.strip() or None, work_id))
    if args.title:
        conn.execute("UPDATE work SET title_en=? WHERE id=?", (args.title.strip(), work_id))
    conn.commit()
    have = conn.execute("SELECT count FROM wish WHERE work_id=?", (work_id,)).fetchone()
    count = args.count if args.count is not None else (have["count"] if have else 1)
    wishlist.set_count(conn, work_id, count)
    print(f"{work_id}: " + (f"on the wishlist, asked for by {wishlist.people(count)}." if count > 0 else "off the wishlist."))
    return 0


def cmd_run(args) -> int:
    from house import orchestrator
    from house.client import make_client

    conn = connect(args.db)
    client = make_client(conn, replay=args.replay, run_cap=args.cap)
    options = {k: v for k, v in (("draft_model", args.draft_model), ("reader_model", args.reader_model),
                                 ("desk_model", args.desk_model), ("final_model", args.final_model)) if v}
    if args.draft_prompt:
        options["draft_prompt"] = args.draft_prompt
    if args.voice is not None:
        if args.voice < 0:
            print("Not run: voices are numbered from 0.")
            return 1
        options["voice"] = args.voice
    if args.checkpoint:
        options["checkpoint"] = True
    if args.from_ or args.only:  # a run waiting at the checkpoint goes on only once it's approved
        rid = args.run or orchestrator.latest_run(conn, args.work)
        row = conn.execute("SELECT status FROM run WHERE id=?", (rid,)).fetchone() if rid else None
        if row and row["status"] == "waiting":
            print(f"Not run: run {rid} is waiting at the checkpoint. Approve a voice first with "
                  f"`keikaku approve {args.work} --voice N`, then run it from the draft.")
            return 1
    from house.budget import CapExceeded, HouseClosed
    from house.client import FixtureMissing

    try:
        run_id = orchestrator.run(conn, client, args.work, to=args.to, from_=args.from_, only=args.only,
                                  run_id=args.run, label=args.label, options=options)
    except (CapExceeded, HouseClosed) as e:
        print(f"Stopped: {e}")
        return 1
    except orchestrator.RunFailed as e:
        if isinstance(e.__cause__, FixtureMissing):
            print(f"Stopped: {args.work} has no recorded run to replay at this point. Without a key, only the "
                  f"recorded works in fixtures/ can be run; with MODEL_API_KEY set, any work in fixtures/works.json "
                  f"or added with `keikaku add` can. ({e.__cause__})")
        else:
            print(f"Stopped: {e}")
        return 1
    except (KeyError, PermissionError) as e:  # an unknown work, or one that fails its rights record
        print(f"Not run: {e.args[0] if e.args else e}")
        return 1
    spent = client.budget.spent(run_id)
    if conn.execute("SELECT status FROM run WHERE id=?", (run_id,)).fetchone()[0] == "waiting":
        print(f"run {run_id}: waiting at the checkpoint, page 1 drafted in each voice; spent ${spent:.4f} live. "
              f"Read it with `keikaku checkpoint {args.work}`, send a note with `keikaku steer {args.work} \"your note\"`, "
              f"approve with `keikaku approve {args.work} --voice N`, then carry on with `keikaku run {args.work} --from draft`.")
        return 0
    status, stage = conn.execute("SELECT status, stage FROM run WHERE id=?", (run_id,)).fetchone()
    print(f"run {run_id}: " + ("done and released" if status == "done" else f"stopped after {stage}")
          + f"; spent ${spent:.4f} live")
    return 0


def _run_of(conn, args) -> int | None:
    """The run a checkpoint command acts on: --run, else the latest run of the work."""
    from house import orchestrator

    run_id = args.run or orchestrator.latest_run(conn, args.work)
    row = conn.execute("SELECT work_id FROM run WHERE id=?", (run_id,)).fetchone() if run_id else None
    if not row or row["work_id"] != args.work:
        print(f"Not done: there is no run of {args.work} in this database.")
        return None
    return run_id


def write_checkpoint(conn, work: str, run_id: int) -> list:
    from house import steer
    from house.db import data_dir

    out = data_dir() / "checkpoints" / work
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, text in steer.markdown(conn, run_id).items():
        (out / name).write_text(text, encoding="utf-8")
        paths.append(out / name)
    return paths


def cmd_checkpoint(args) -> int:
    from house import steer

    conn = connect(args.db)
    run_id = _run_of(conn, args)
    if run_id is None:
        return 1
    try:
        paths = write_checkpoint(conn, args.work, run_id)
    except steer.NotWaiting as e:
        print(f"Not done: {e}.")
        return 1
    status = conn.execute("SELECT status FROM run WHERE id=?", (run_id,)).fetchone()[0]
    for p in paths:
        print(p)
    if status != "waiting":
        print(f"run {run_id} is no longer waiting ({status}): these are what it was approved from.")
    return 0


def cmd_steer(args) -> int:
    from house import steer
    from house.budget import CapExceeded, HouseClosed
    from house.client import FixtureMissing, make_client

    conn = connect(args.db)
    run_id = _run_of(conn, args)
    if run_id is None:
        return 1
    client = make_client(conn, replay=args.replay, run_cap=args.cap)
    try:
        rnd = steer.steer(conn, client, run_id, args.note)
    except (steer.NotWaiting, ValueError) as e:
        print(f"Not sent: {e}.")
        return 1
    except FixtureMissing:
        print("Not sent: a note needs a live call, and there is no MODEL_API_KEY (or --replay was given).")
        return 1
    except (CapExceeded, HouseClosed) as e:
        print(f"Stopped: {e}")
        return 1
    print(rnd["reply"])
    if rnd["changed"]:
        print("\nChanged:")
        for c in rnd["changed"]:
            print(f"- {c}")
    else:
        print("\nNothing in the reading or the bible changed.")
    if rnd["question"]:
        print(f"\nThe house asks: {rnd['question']}")
    print(f"\nPage 1 was drafted again in voice {rnd['voice']} ({rnd['take']['label']}). The files are updated:")
    for p in write_checkpoint(conn, args.work, run_id):
        print(p)
    print(f"spent ${client.budget.spent(run_id):.4f} live on this run so far")
    return 0


def cmd_approve(args) -> int:
    from house import steer

    conn = connect(args.db)
    run_id = _run_of(conn, args)
    if run_id is None:
        return 1
    try:
        steer.approve(conn, run_id, args.voice)
    except (steer.NotWaiting, ValueError) as e:
        print(f"Not approved: {e}.")
        return 1
    print(f"run {run_id}: approved in voice {args.voice}. Carry on with `keikaku run {args.work} --from draft"
          + (f" --run {run_id}`." if args.run else "`."))
    return 0


def cmd_fixture(args) -> int:
    from house import fixture, orchestrator

    conn = connect(args.db)
    run_id = args.run or orchestrator.latest_run(conn, args.work)
    print(fixture.export(conn, args.work, run_id))
    return 0


def cmd_download(args) -> int:
    from pathlib import Path

    from house import fixture, orchestrator

    conn = connect(args.db)
    run_id = args.run or orchestrator.latest_run(conn, args.work)
    row = conn.execute("SELECT work_id FROM run WHERE id=?", (run_id,)).fetchone() if run_id else None
    if not row or row["work_id"] != args.work:
        print(f"Not downloaded: no such run of {args.work} in this database.")
        return 1
    out = Path(args.out or f"{args.work}-run{run_id}.zip")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(fixture.download(conn, run_id))
    print(out)
    return 0


def cmd_audit(args) -> int:
    import json

    from house import audit
    from house.client import make_client

    conn = connect(args.db)
    client = make_client(conn, replay=args.replay, run_cap=args.cap)
    work = works.parse(args.work, conn)
    versions = [(f"run-{r}", audit.run_english(conn, r)) for r in args.runs]
    if args.baseline:
        versions.append(("one-shot", audit.baseline(client, work)))
    for label, english in versions:
        print(json.dumps(audit.summary(audit.audit(client, conn, work, label, english)), ensure_ascii=False))
        if args.readable:
            r = audit.audit_readable(client, conn, work, label, english)
            marks = r["audit"]["marks"]
            print(json.dumps({"label": label, "readable_marks": len(marks),
                              "serious": sum(m["severity"] == "serious" for m in marks),
                              "overall": r["audit"]["overall"], "usd": round(r["usd"], 4)}, ensure_ascii=False))
    return 0


def cmd_serve(args) -> int:
    from house import web

    web.serve(args.db, replay=args.replay or args.serve_replay, host=args.host, port=args.port)
    return 0


def cmd_invite(args) -> int:
    import os

    from dotenv import load_dotenv

    from house import desk
    from house.db import ROOT

    load_dotenv(ROOT / ".env")  # KEIKAKU_SECRET salts the token's hash; the site must hash it the same way
    conn = connect(args.db)
    if args.list:
        for i in desk.invites(conn):
            state = f"revoked {i['revoked']}" if i["revoked"] else f"last used {i['last_used'] or 'never'}"
            print(f"{i['id']:>4}  {i['name']:<30} {i['left']:>7,} drops left  made {i['created']}  {state}")
        return 0
    if args.revoke:
        if not desk.revoke(conn, args.revoke):
            print("no such invite", file=sys.stderr)
            return 1
        print("revoked")
        return 0
    if not args.name:
        print("give a name, or --list or --revoke", file=sys.stderr)
        return 2
    token = desk.invite(conn, args.name, drops=args.drops, work=args.work)
    base = (args.base_url or os.environ.get("KEIKAKU_BASE_URL") or "http://127.0.0.1:8000").rstrip("/")
    print(f"{base}/desk/{token}")
    return 0


def cmd_comments(args) -> int:
    from dotenv import load_dotenv

    from house import comments
    from house.db import ROOT

    load_dotenv(ROOT / ".env")  # KEIKAKU_SECRET signs the links in the email
    conn = connect(args.db)
    if args.hide or args.restore:
        cid = args.hide or args.restore
        done = comments.hide(conn, cid, "hidden by the editor") if args.hide else comments.restore(conn, cid)
        print(("hidden" if args.hide else "published") if done else "nothing to change")
        return 0 if done else 1
    if args.email:
        since = conn.execute("SELECT datetime('now', ?)", (f"-{args.days} days",)).fetchone()[0]
        mail = comments.digest_email(conn, since)
        print(f"{mail[0]}\n\n{mail[1]}" if mail else "nothing in that time")
        return 0
    where = "" if args.status == "all" else "WHERE status = ?"
    for r in conn.execute(f"SELECT c.*, (SELECT COUNT(*) FROM comment_report r WHERE r.comment_id = c.id) AS reports "
                          f"FROM comment c {where} ORDER BY id DESC LIMIT ?",
                          (() if args.status == "all" else (args.status,)) + (args.limit,)):
        extra = "; ".join(x for x in [f"{r['reports']} reports" if r["reports"] else "", r["reason"] or ""] if x)
        print(f"#{r['id']:<5} {r['created_at']}  {r['status']:<9} {r['work_id']} {r['segment_id']}  {r['name'] or '-'}"
              + (f"  ({extra})" if extra else "") + f"\n       {r['body'][:200]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="keikaku", description="Run the translation house.")
    parser.add_argument("--db", help="SQLite file (default keikaku.db in KEIKAKU_DATA_DIR, else var/)")
    parser.add_argument("--replay", action="store_true", help="no live calls: serve recorded responses only")
    parser.add_argument("--cap", type=float, help="run cap in dollars (default KEIKAKU_CAP_RUN)")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("fetch", help="fetch works from Aozora into fixtures/sources")
    p.add_argument("works", nargs="*")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("add", help="add a work from a link to its page on Aozora Bunko, if it passes the rights rule")
    p.add_argument("url", help="the work's card, https://www.aozora.gr.jp/cards/<author>/card<n>.html, or a file on it")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("wish", help="put a work from Aozora on the public wishlist, set its count, or list the wishlist")
    p.add_argument("url", nargs="?", help="the work's card on Aozora Bunko; leave out to print the list")
    p.add_argument("--count", type=int, help="how many people asked for it (default 1 for a new one; 0 takes it off)")
    p.add_argument("--summary", help="one or two sentences about the work, shown on the wishlist and the desk")
    p.add_argument("--title", help="the English title, in place of the one the work card gave it")
    p.set_defaults(func=cmd_wish)

    from house.orchestrator import DEFAULTS, NAMES

    p = sub.add_parser("run", help="run a work through the house, or part of it")
    p.add_argument("work")
    p.add_argument("--to", choices=NAMES, help="stop after this stage")
    p.add_argument("--from", dest="from_", choices=NAMES, help="resume the latest run from this stage")
    p.add_argument("--only", choices=NAMES, help="run one stage of the latest run")
    p.add_argument("--run", type=int, help="the run to resume (default: the latest for this work)")
    p.add_argument("--label")
    for stage in ("draft", "reader", "desk", "final"):
        p.add_argument(f"--{stage}-model", choices=["spark", "wonder"], help=f"model for the {stage} calls (default {DEFAULTS[stage + '_model']})")
    p.add_argument("--draft-prompt", help=f"drafting prompt: translate-draft-plain or translate-draft (default {DEFAULTS['draft_prompt']})")
    p.add_argument("--voice", type=int, help="which of the reading's voice takes to draft in, from 0 (default the first)")
    p.add_argument("--checkpoint", action="store_true",
                   help="stop after the bible with page 1 drafted in each voice, to be steered and approved")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("checkpoint", help="write a waiting run's reading, bible and voices as Markdown in the data folder")
    p.add_argument("work")
    p.add_argument("--run", type=int, help="default: the latest run of this work")
    p.set_defaults(func=cmd_checkpoint)

    p = sub.add_parser("steer", help="send a note on a waiting run: the house amends the reading and bible and redrafts page 1")
    p.add_argument("work")
    p.add_argument("note", help="the note, in your own words")
    p.add_argument("--run", type=int, help="default: the latest run of this work")
    p.set_defaults(func=cmd_steer)

    p = sub.add_parser("approve", help="approve a waiting run in a voice, so it can carry on from the draft")
    p.add_argument("work")
    p.add_argument("--voice", type=int, required=True, help="the voice to draft in, from 0, as voices.md numbers them")
    p.add_argument("--run", type=int, help="default: the latest run of this work")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("fixture", help="export a recorded run to fixtures/<work>/ for replay and the site")
    p.add_argument("work")
    p.add_argument("--run", type=int)
    p.set_defaults(func=cmd_fixture)

    p = sub.add_parser("download", help="a run as a zip for the editor: the full record and the finished editions")
    p.add_argument("work")
    p.add_argument("--run", type=int, help="default: the latest run of this work")
    p.add_argument("--out", help="the zip to write (default <work>-run<N>.zip here)")
    p.set_defaults(func=cmd_download)

    p = sub.add_parser("audit", help="blind audit of runs' English, beside the one-shot baseline")
    p.add_argument("work")
    p.add_argument("--runs", type=int, nargs="*", default=[])
    p.add_argument("--baseline", action="store_true", help="also audit a one-shot Spark translation")
    p.add_argument("--readable", action="store_true", help="also run the blind readability audit")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("serve", help="serve the site; with --replay, the recorded runs in fixtures/ and no key")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--replay", dest="serve_replay", action="store_true", help="serve fixtures/ only")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("invite", help="make an invite link to the editors' desk, with an allowance; or list or revoke them")
    p.add_argument("name", nargs="?", help="the editor's name")
    p.add_argument("--drops", type=int, default=4000, help="allowance in drops (default 4000)")
    p.add_argument("--work", choices=list(works.registry()), help="a work to suggest on the desk")
    p.add_argument("--base-url", help="the site's address (default KEIKAKU_BASE_URL, else http://127.0.0.1:8000)")
    p.add_argument("--revoke", metavar="TOKEN_OR_ID", help="revoke an invite by its token or id")
    p.add_argument("--list", action="store_true", help="list invites: name, drops left, made, revoked")
    p.set_defaults(func=cmd_invite)

    p = sub.add_parser("comments", help="list readers' comments, hide or restore one, or print the daily email")
    p.add_argument("--status", default="all", choices=["all", "published", "failed", "hidden", "pending"])
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--hide", type=int, metavar="ID", help="hide a published comment (it stays in the database)")
    p.add_argument("--restore", type=int, metavar="ID", help="publish a hidden or failed comment")
    p.add_argument("--email", action="store_true", help="print the editor's email for the last --days, without sending it")
    p.add_argument("--days", type=int, default=1)
    p.set_defaults(func=cmd_comments)

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
