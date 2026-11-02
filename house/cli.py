"""The keikaku command line."""

import argparse
import sys

from house import works
from house.db import connect


def cmd_fetch(args) -> int:
    for wid in args.works or list(works.registry()):
        print(wid, works.fetch(wid))
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
                  f"recorded works in fixtures/ can be run; with MODEL_API_KEY set, any work in fixtures/works.json can. ({e.__cause__})")
        else:
            print(f"Stopped: {e}")
        return 1
    except (KeyError, PermissionError) as e:  # an unknown work, or one that fails its rights record
        print(f"Not run: {e.args[0] if e.args else e}")
        return 1
    spent = client.budget.spent(run_id)
    print(f"run {run_id}: stopped after {conn.execute('SELECT stage FROM run WHERE id=?', (run_id,)).fetchone()[0]}; "
          f"spent ${spent:.4f} live")
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
    out.write_bytes(fixture.download(conn, run_id))
    print(out)
    return 0


def cmd_audit(args) -> int:
    import json

    from house import audit
    from house.client import make_client

    conn = connect(args.db)
    client = make_client(conn, replay=args.replay, run_cap=args.cap)
    work = works.parse(args.work)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="keikaku", description="Run the translation house.")
    parser.add_argument("--db", help="SQLite file (default keikaku.db in KEIKAKU_DATA_DIR, else var/)")
    parser.add_argument("--replay", action="store_true", help="no live calls: serve recorded responses only")
    parser.add_argument("--cap", type=float, help="run cap in dollars (default KEIKAKU_CAP_RUN)")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("fetch", help="fetch works from Aozora into fixtures/sources")
    p.add_argument("works", nargs="*")
    p.set_defaults(func=cmd_fetch)

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
    p.set_defaults(func=cmd_run)

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

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
