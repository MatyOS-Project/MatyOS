"""The `matyos` command-line interface.

Usage:
    matyos check <path>         Type-check a .elk file, a project directory, or
                                a .matyos archive (prints a scientific report).
    matyos new <name>           Scaffold a new MatyOS project.
    matyos pack <dir> [out]     Pack a project directory into a .matyos archive.
    matyos unpack <file> [dir]  Extract a .matyos archive.
    matyos version              Print the version.
    matyos help                 Show this help.
"""

import os
import sys

from matyos import __version__

USAGE = """matyos <command> [args]

Commands:
  check <path>          check a .elk file, a project dir, or a .matyos archive
  new <name>            scaffold a new MatyOS project
  build <dir> [out]     seal a COMPLETED project into a compressed .matyos
  info <file.matyos>    show a sealed archive's manifest (no re-checking)
  pack <dir> [out]      pack a project directory into a .matyos (no checking)
  unpack <file> [dir]   extract a .matyos archive
  version               print the MatyOS version
  help                  show this help

Files in a MatyOS project:
  .thm  theorem statements      .prf  proofs (kernel-checked)
  .hyp  hypotheses/conjectures  .test computational tests
  .elk  definitions & datatypes

Examples:
  matyos new my_theory
  matyos check my_theory
  matyos pack my_theory
  matyos check my_theory.matyos
"""


def _run_file(path):
    from matyos.frontend.surface import run_file, ParseError
    from matyos.kernel.core import TypeError_, reset_environment
    reset_environment()
    try:
        failures = run_file(path) or 0
    except FileNotFoundError:
        print(f"matyos: file not found: {path}", file=sys.stderr)
        return 2
    except (ParseError, TypeError_) as e:
        print(f"matyos: error in {path}:\n  {e}", file=sys.stderr)
        return 1
    if failures:
        print(f"matyos: {failures} check(s) FAILED in {path}", file=sys.stderr)
        return 1
    return 0


def _run_project(path):
    from matyos.project.engine import check_project
    report, failures = check_project(path)
    print(report)
    return 1 if failures else 0


def _check(path):
    if not os.path.exists(path):
        print(f"matyos: path not found: {path}", file=sys.stderr)
        return 2
    if os.path.isdir(path) or path.endswith(".matyos"):
        return _run_project(path)
    return _run_file(path)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(USAGE)
        return 0
    cmd, rest = argv[0], argv[1:]

    if cmd in ("version", "--version", "-v"):
        print(f"MatyOS {__version__}")
        return 0
    if cmd in ("help", "--help", "-h"):
        print(USAGE)
        return 0
    if cmd in ("check", "eval"):
        if not rest:
            print(f"matyos: '{cmd}' needs a path, e.g. matyos check my_theory",
                  file=sys.stderr)
            return 2
        return _check(rest[0])
    if cmd == "new":
        if not rest:
            print("matyos: 'new' needs a project name", file=sys.stderr)
            return 2
        from matyos.project.engine import scaffold
        try:
            scaffold(rest[0])
        except FileExistsError as e:
            print(f"matyos: {e}", file=sys.stderr)
            return 1
        print(f"Created project '{rest[0]}'.  Try:  matyos check {rest[0]}")
        return 0
    if cmd == "build":
        if not rest:
            print("matyos: 'build' needs a project directory", file=sys.stderr)
            return 2
        from datetime import datetime, timezone
        from matyos.project.engine import build_project
        force = "--force" in rest
        rest = [a for a in rest if a != "--force"]
        out = rest[1] if len(rest) > 1 else None
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        res = build_project(rest[0], out=out, force=force, timestamp=ts)
        print(res["report"])
        if res["out"]:
            s = res["manifest"]["summary"]
            seal = "sealed" if res["completed"] else "packed (forced, INCOMPLETE)"
            print(f"\n{seal} -> {res['out']}  "
                  f"({s['certified']} certified, {s['conditional']} conditional, "
                  f"{s['open']} open)")
            return 0 if res["completed"] else 1
        print("\nmatyos: project is NOT complete (open theorems or failed checks); "
              "not sealed. Use 'matyos build <dir> --force' to archive anyway.",
              file=sys.stderr)
        return 1
    if cmd == "info":
        if not rest:
            print("matyos: 'info' needs a .matyos file", file=sys.stderr)
            return 2
        from matyos.project.engine import read_manifest
        m = read_manifest(rest[0])
        if not m:
            print("matyos: no manifest in archive (build it with 'matyos build')",
                  file=sys.stderr)
            return 1
        s = m["summary"]
        print(f"{m['name']}  (MatyOS {m.get('matyos_version','?')}, "
              f"built {m.get('generated','?')})")
        print(f"  completed : {m['completed']}")
        print(f"  theorems  : {s['theorems_proven']} proven "
              f"({s['certified']} certified, {s['conditional']} conditional), "
              f"{s['open']} open")
        print(f"  conjectures: {s['conjectures']} (realistic)")
        print(f"  tests     : {s['tests_passed']} passed, {s['tests_failed']} failed")
        print(f"  theories  : {', '.join(m['theories'].keys())}")
        return 0
    if cmd == "pack":
        if not rest:
            print("matyos: 'pack' needs a directory", file=sys.stderr)
            return 2
        from matyos.project.engine import pack
        out = pack(rest[0], rest[1] if len(rest) > 1 else None)
        print(f"Packed -> {out}")
        return 0
    if cmd == "unpack":
        if not rest:
            print("matyos: 'unpack' needs a .matyos file", file=sys.stderr)
            return 2
        from matyos.project.engine import unpack
        dest = unpack(rest[0], rest[1] if len(rest) > 1 else None)
        print(f"Unpacked -> {dest}")
        return 0
    # bare path -> check it
    if os.path.exists(cmd) or cmd.endswith((".elk", ".matyos")):
        return _check(cmd)
    print(f"matyos: unknown command '{cmd}'. Try 'matyos help'.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
