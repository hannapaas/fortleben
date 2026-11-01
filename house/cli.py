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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="keikaku", description="Run the translation house.")
    parser.add_argument("--db", help="SQLite file (default var/keikaku.db)")
    parser.add_argument("--replay", action="store_true", help="no live calls: serve recorded responses only")
    parser.add_argument("--cap", type=float, help="run cap in dollars (default KEIKAKU_CAP_RUN)")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("fetch", help="fetch works from Aozora into fixtures/sources")
    p.add_argument("works", nargs="*")
    p.set_defaults(func=cmd_fetch)

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
