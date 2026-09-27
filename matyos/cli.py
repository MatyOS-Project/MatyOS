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
  check <path> [--json] check a .elk file, project dir, or .matyos archive
                        (--json emits a machine-readable result for tools/LLMs)
  new <name>            scaffold a new MatyOS project
  build <dir> [out]     seal a COMPLETED project into a compressed .matyos
  info <file.matyos>    show a sealed archive's manifest (no re-checking)
  pack <dir> [out]      pack a project directory into a .matyos (no checking)
  unpack <file> [dir]   extract a .matyos archive
  realistic <claim>     judge a bound "a <= b" with Stoqos (three-valued logic)
                        [--domain <name>] judge in a domain (e.g. triangles)
                        [--batch <file>]  judge every claim in a file (one/line)
                        [--json] emit a machine-readable Judgement
  discover              run the v2 discovery-engine toy loop (experimental)
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
  matyos realistic "radius <= diameter"
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


def _check_json(path):
    """Emit a structured JSON result for tools / LLMs instead of pretty text."""
    import json
    from matyos.kernel.core import reset_environment
    reset_environment()
    if os.path.isdir(path) or path.endswith(".matyos"):
        from matyos.project.engine import analyze_project
        _, failures, manifest = analyze_project(path)
        manifest["failures"] = failures
        print(json.dumps(manifest, indent=2))
        return 1 if failures else 0
    from matyos.frontend.surface import Checker, ParseError
    from matyos.kernel.core import TypeError_
    checker = Checker()
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            checker.run_text(f.read(), echo=False)
        out = {"kind": "file", "path": path, "failures": checker.failures,
               "events": checker.events}
    except (ParseError, TypeError_, FileNotFoundError) as e:
        out = {"kind": "file", "path": path, "failures": 1,
               "error": str(e), "events": checker.events}
    print(json.dumps(out, indent=2))
    return 1 if out["failures"] else 0


def _resolve_stdlib(path):
    """Let `stdlib/<name>.elk` (or a bare bundled name) resolve to the packaged
    standard library, so `matyos check stdlib/arith.elk` works from a checkout and
    after a plain pip install alike. A real path on disk always wins."""
    if os.path.exists(path):
        return path
    base = os.path.basename(path)
    if base.endswith(".elk"):
        try:
            from importlib.resources import files
            cand = files("matyos").joinpath("stdlib", base)
            if cand.is_file():
                return str(cand)
        except Exception:
            pass
    return path


def _check(path, as_json=False):
    path = _resolve_stdlib(path)
    if not os.path.exists(path):
        print(f"matyos: path not found: {path}", file=sys.stderr)
        return 2
    if as_json:
        return _check_json(path)
    if os.path.isdir(path) or path.endswith(".matyos"):
        return _run_project(path)
    return _run_file(path)


# The verdict of the REALISTIC three-valued logic, in plain English. TRUE means
# the kernel / known-facts database proved it (never the score alone); REALISTIC is
# the paper's middle value (held on evidence, unproven); FALSE has a counterexample;
# UNKNOWN is "cannot be judged", not a truth value.
_TRUTH_LINE = {
    "true":      "TRUE        proven — a known theorem (the kernel decides TRUE)",
    "realistic": "REALISTIC   holds on all evidence, but unproven",
    "false":     "FALSE       a counterexample exists in the evidence",
    "unknown":   "UNKNOWN     cannot be judged (out of domain / unparseable)",
}


def _realistic(claim, as_json=False, domain=None):
    """Run the Stoqos flow on one bound `a <= b` and print its honest verdict.

    This is the diagram in `docs/stoqos.md` made runnable: kernel-style evidence
    test -> FALSE / UNKNOWN, otherwise Stoqos scores -> REALISTIC / UNCERTAIN.
    Stoqos only scores plausibility; the kernel decides real TRUE.

    Without `domain`, `a` and `b` are graph invariants. With `--domain <name>`
    they are functionals of that domain (e.g. `triangles`), so real statements
    outside graphs become judgeable.
    """
    from matyos.discovery import stoqos
    if domain:
        from matyos.discovery import domains as D
        doms = {d.name: d for d in D.all_domains()}
        if domain not in doms:
            print(f"matyos: unknown domain '{domain}'. Available: "
                  f"{', '.join(sorted(doms))}", file=sys.stderr)
            return 2
        j = stoqos.judge_domain(doms[domain], claim)
    else:
        j = stoqos.judge(claim)
    truth = stoqos.truth3(j)                 # true / false / realistic / unknown
    if as_json:
        import json
        print(json.dumps({"claim": claim, "truth": truth, "verdict": j.verdict,
                          "value": j.value, "confidence": j.confidence,
                          "known": j.known, "backend": j.backend,
                          "note": j.note}, indent=2))
        return 0
    print(f"claim:    {claim}")
    print(f"verdict:  {_TRUTH_LINE.get(truth, truth)}")
    if truth == "realistic" and j.value is not None:
        print(f"value:    P(true) = {j.value:.2f}  (calibrated, confidence {j.confidence:.2f})")
    print(f"note:     {j.note}")
    return 0


def _realistic_batch(path, as_json=False, domain=None):
    """Judge every claim in a file (one `a <= b` per line; blanks and #comments
    skipped) and print a compact TRUE/FALSE/REALISTIC/UNKNOWN table."""
    from matyos.discovery import stoqos
    try:
        with open(path, encoding="utf-8") as f:
            claims = [ln.strip() for ln in f
                      if ln.strip() and not ln.lstrip().startswith("#")]
    except OSError as e:
        print(f"matyos: cannot read {path}: {e}", file=sys.stderr)
        return 2
    if not claims:
        print(f"matyos: no claims in {path}", file=sys.stderr)
        return 2
    dom = None if not domain or domain == "graphs" else domain
    results = stoqos.judge_many(claims, domain=dom)
    if as_json:
        import json
        print(json.dumps([{"claim": c, "truth": stoqos.truth3(j), "value": j.value}
                          for c, j in zip(claims, results)], indent=2))
        return 0
    width = min(max((len(c) for c in claims), default=10), 48)
    for c, j in zip(claims, results):
        t = stoqos.truth3(j)
        tag = t.upper()
        if t == "realistic" and j.value is not None:
            tag += f"  {j.value:.2f}"
        print(f"{c[:width]:<{width}}  {tag}")
    return 0


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
        as_json = "--json" in rest
        rest = [a for a in rest if a != "--json"]
        if not rest:
            print(f"matyos: '{cmd}' needs a path, e.g. matyos check my_theory",
                  file=sys.stderr)
            return 2
        return _check(rest[0], as_json=as_json)
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
    if cmd == "realistic":
        as_json = "--json" in rest
        rest = [a for a in rest if a != "--json"]
        domain = batch = None
        i = 0
        while i < len(rest):
            a = rest[i]
            if a == "--domain" and i + 1 < len(rest):
                domain = rest[i + 1]; rest = rest[:i] + rest[i + 2:]; continue
            if a.startswith("--domain="):
                domain = a.split("=", 1)[1]; rest = rest[:i] + rest[i + 1:]; continue
            if a == "--batch" and i + 1 < len(rest):
                batch = rest[i + 1]; rest = rest[:i] + rest[i + 2:]; continue
            if a.startswith("--batch="):
                batch = a.split("=", 1)[1]; rest = rest[:i] + rest[i + 1:]; continue
            i += 1
        if batch:
            return _realistic_batch(batch, as_json=as_json, domain=domain)
        if not rest:
            print('matyos: \'realistic\' needs a claim, e.g. '
                  'matyos realistic "radius <= diameter"', file=sys.stderr)
            return 2
        return _realistic(" ".join(rest), as_json=as_json, domain=domain)
    if cmd == "discover":
        # Experimental v2 discovery engine. Runs the built-in toy loop for now.
        # `--json` emits structured results for the dashboard / tooling.
        from matyos.discovery.__main__ import main as discover_main
        return discover_main(rest)
    # bare path -> check it
    if os.path.exists(cmd) or cmd.endswith((".elk", ".matyos")):
        return _check(cmd)
    print(f"matyos: unknown command '{cmd}'. Try 'matyos help'.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
