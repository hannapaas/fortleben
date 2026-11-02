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

    p = sub.add_parser("audit", help="blind audit of runs' English, beside the one-shot baseline")
    p.add_argument("work")
    p.add_argument("--runs", type=int, nargs="*", default=[])
    p.add_argument("--baseline", action="store_true", help="also audit a one-shot Spark translation")
    p.add_argument("--readable", action="store_true", help="also run the blind readability audit")
    p.set_defaults(func=cmd_audit)

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
