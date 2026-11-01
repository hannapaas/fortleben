"""The keikaku command line."""

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="keikaku", description="Run the translation house.")
    parser.add_subparsers(dest="command")
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
