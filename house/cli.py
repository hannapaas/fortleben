"""The keikaku command line."""

import argparse
import sys

from house import works
from house.db import connect


def cmd_fetch(args) -> int:
    for wid in args.works or list(works.registry()):
        print(wid, works.fetch(wid))
    return 0


def cmd_calibrate(args) -> int:
    from house import calibrate
    from house.client import make_client

    conn = connect(args.db)
    client = make_client(conn, replay=args.replay, run_cap=args.cap)
    rows = calibrate.run(client, works.parse(args.work))
    print(calibrate.table(rows))
    return 0


def cmd_run(args) -> int:
    from house import orchestrator
    from house.client import make_client

    conn = connect(args.db)
    client = make_client(conn, replay=args.replay, run_cap=args.cap)
    options = {}
    if args.compare_referents is not None:
        options["compare_referents"] = args.compare_referents
    run_id = orchestrator.run(conn, client, args.work, to=args.to, from_=args.from_, only=args.only,
                              run_id=args.run, label=args.label, options=options)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="keikaku", description="Run the translation house.")
    parser.add_argument("--db", help="SQLite file (default var/keikaku.db)")
    parser.add_argument("--replay", action="store_true", help="no live calls: serve recorded responses only")
    parser.add_argument("--cap", type=float, help="run cap in dollars (default KEIKAKU_CAP_RUN)")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("fetch", help="fetch works from Aozora into fixtures/sources")
    p.add_argument("works", nargs="*")
    p.set_defaults(func=cmd_fetch)

    from house.orchestrator import NAMES

    p = sub.add_parser("run", help="run a work through the house, or part of it")
    p.add_argument("work")
    p.add_argument("--to", choices=NAMES, help="stop after this stage")
    p.add_argument("--from", dest="from_", choices=NAMES, help="resume the latest run from this stage")
    p.add_argument("--only", choices=NAMES, help="run one stage of the latest run")
    p.add_argument("--run", type=int, help="the run to resume (default: the latest for this work)")
    p.add_argument("--label")
    p.add_argument("--compare-referents", type=int, metavar="PAGES",
                   help="also draft the first PAGES pages without referent entries, for comparison")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("fixture", help="export a recorded run to fixtures/<work>/ for replay and the site")
    p.add_argument("work")
    p.add_argument("--run", type=int)
    p.set_defaults(func=cmd_fixture)

    p = sub.add_parser("calibrate", help="M0: first real calls and reasoning-token costs")
    p.add_argument("work", nargs="?", default="bansan")
    p.set_defaults(func=cmd_calibrate)

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
