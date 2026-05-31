"""The `matyos` command-line interface.

Usage:
    matyos check <file.elk>     Type-check a proof file.
    matyos eval  <file.elk>     Same as check (echoes eval/check results).
    matyos version              Print the version.
    matyos help                 Show this help.
"""

import argparse
import sys

from matyos import __version__

USAGE = """matyos <command> [args]

Commands:
  check <file.elk>    type-check a proof file
  eval  <file.elk>    type-check, echoing eval/check results
  version             print the MatyOS version
  help                show this help

Examples:
  matyos check stdlib/arith.elk
  matyos version
"""


def _run(path):
    # imported lazily so `matyos version`/`help` start instantly
    from matyos.frontend.surface import run_file, ParseError
    from matyos.kernel.core import TypeError_
    try:
        failures = run_file(path) or 0
        if failures:
            print(f"matyos: {failures} proof(s) FAILED in {path}", file=sys.stderr)
            return 1
        return 0
    except FileNotFoundError:
        print(f"matyos: file not found: {path}", file=sys.stderr)
        return 2
    except (ParseError, TypeError_) as e:
        print(f"matyos: error in {path}:\n  {e}", file=sys.stderr)
        return 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(USAGE)
        return 0

    parser = argparse.ArgumentParser(prog="matyos", add_help=False, usage=USAGE)
    parser.add_argument("command")
    parser.add_argument("args", nargs="*")
    ns, _ = parser.parse_known_args(argv)

    cmd = ns.command
    if cmd in ("version", "--version", "-v"):
        print(f"MatyOS {__version__}")
        return 0
    if cmd in ("help", "--help", "-h"):
        print(USAGE)
        return 0
    if cmd in ("check", "eval"):
        if not ns.args:
            print(f"matyos: '{cmd}' needs a file, e.g. matyos {cmd} stdlib/arith.elk",
                  file=sys.stderr)
            return 2
        return _run(ns.args[0])
    # bare path -> check it
    if cmd.endswith(".elk"):
        return _run(cmd)
    print(f"matyos: unknown command '{cmd}'. Try 'matyos help'.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
