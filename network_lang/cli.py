from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .parser import ParseError, parse_file
from .validation import validate_operations

COMMANDS = {"parse", "validate"}


def main(argv: Sequence[str] | None = None) -> int:
    """

    Args:
        argv:

    Returns:

    """
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    had_error = False

    for path in args.files:
        try:
            operations = parse_file(path)
        except OSError as error:
            print(f"{path}: {error}", file=sys.stderr)
            had_error = True
            continue
        except ParseError as error:
            print(error, file=sys.stderr)
            had_error = True
            continue

        if args.command == "parse":
            print(json.dumps([operation.to_dict() for operation in operations], indent=2))
            continue

        diagnostics = validate_operations(operations)
        for diagnostic in diagnostics:
            print(
                f"{diagnostic.label()}: {diagnostic.level}: {diagnostic.message}",
                file=sys.stderr if diagnostic.is_error else sys.stdout,
            )
        if any(diagnostic.is_error for diagnostic in diagnostics):
            had_error = True
        elif not args.quiet:
            print(f"OK {path} ({len(operations)} operations)")

    return 1 if had_error else 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """

    Args:
        argv:

    Returns:

    """
    if argv and argv[0] not in COMMANDS and not argv[0].startswith("-"):
        argv = ["validate", *argv]

    parser = argparse.ArgumentParser(
        prog="uns",
        description="Parse and validate Unified Network Syntax files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate .uns files")
    validate.add_argument("files", nargs="+", type=Path)
    validate.add_argument("-q", "--quiet", action="store_true")

    parse = subparsers.add_parser("parse", help="print parsed operations as JSON")
    parse.add_argument("files", nargs="+", type=Path)
    parse.set_defaults(quiet=False)

    return parser.parse_args(argv)

