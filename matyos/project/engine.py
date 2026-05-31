"""
MatyOS projects — the scientific method as a file system.

A MatyOS *project* is a collection of files (a "sigma of files"). Each file has
a role:

    .hyp    hypotheses / conjectures   (assumed truths — epistemically realistic)
    .thm    theorem statements         (the propositions we aim to establish)
    .test   tests / experiments        (computational checks of our claims)
    .prf    proofs                     (kernel-checked derivations that certify a theorem)
    .elk    definitions & datatypes    (the shared vocabulary)

A *theory* is a sub-directory grouping its .thm + .prf (and friends) — a body of
verified knowledge. A whole project can be packed into a single `.matyos`
archive (a zip), the project's distributable form.

`check_project` runs the files in scientific-method order
(definitions -> hypotheses -> theorems -> tests -> proofs) through one shared
kernel session, then reports each theorem's status:

    PROVEN (certified)     — kernel-checked, depends on no conjecture
    PROVEN (conditional)   — kernel-checked, but relies on an open conjecture (realistic)
    OPEN                   — stated, not yet proven
"""

import os
import zipfile
import tempfile
import shutil

from matyos.kernel import core
from matyos.frontend.surface import Checker, ParseError

KIND_BY_EXT = {".elk": "elk", ".hyp": "hyp", ".thm": "thm",
               ".test": "test", ".prf": "prf"}
PHASE = {"elk": 0, "hyp": 1, "thm": 2, "test": 3, "prf": 4}

BAR = "=" * 58
DASH = "-" * 58


def _discover(root):
    """Return [(theory, relpath, kind, abspath), ...] for known file types."""
    found = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            kind = KIND_BY_EXT.get(ext)
            if not kind:
                continue
            abspath = os.path.join(dirpath, fn)
            rel = os.path.relpath(abspath, root).replace("\\", "/")
            theory = os.path.dirname(rel) or "(root)"
            found.append((theory, rel, kind, abspath))
    # scientific-method order globally, then by path for determinism
    found.sort(key=lambda t: (PHASE[t[2]], t[0], t[1]))
    return found


def check_project(path):
    """Check a project directory or a .matyos archive.
    Returns (report_text, failure_count)."""
    tmp = None
    try:
        if os.path.isfile(path) and path.endswith(".matyos"):
            tmp = tempfile.mkdtemp(prefix="matyos_")
            with zipfile.ZipFile(path) as z:
                z.extractall(tmp)
            root = tmp
            name = os.path.splitext(os.path.basename(path))[0]
        else:
            root = path
            name = os.path.basename(os.path.normpath(path)) or "project"

        core.reset_environment()
        checker = Checker()
        files = _discover(root)
        per_file = []  # (theory, rel, kind, events_slice)
        for theory, rel, kind, abspath in files:
            start = len(checker.events)
            with open(abspath, "r", encoding="utf-8-sig") as f:
                text = f.read()
            try:
                checker.run_text(text, echo=False)
            except (ParseError, core.TypeError_, Exception) as e:
                checker.failures += 1
                checker.events.append({"kind": "error", "name": rel,
                                       "status": "ERROR", "detail": str(e),
                                       "deps": []})
            per_file.append((theory, rel, kind, checker.events[start:]))

        report = _format(name, per_file, checker)
        return report, checker.failures
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def _theorem_status(checker, name):
    if name in checker.proven:
        deps = checker.cond_deps.get(name) or set()
        if deps:
            return "PROVEN", "conditional on: " + ", ".join(sorted(deps))
        return "PROVEN", "certified"
    return "OPEN", "no proof yet"


def _format(name, per_file, checker):
    # group events by theory
    theories = {}
    for theory, rel, kind, evs in per_file:
        theories.setdefault(theory, []).extend(evs)

    lines = [BAR, f" MatyOS project: {name}", BAR, ""]
    for theory in sorted(theories):
        evs = theories[theory]
        defs = [e for e in evs if e["kind"] in ("def", "inductive", "axiom")]
        hyps = [e for e in evs if e["kind"] in ("hypothesis", "conjecture")]
        thms = [e for e in evs if e["kind"] == "theorem"]
        tests = [e for e in evs if e["kind"] == "test"]
        errs = [e for e in evs if e["kind"] == "error"]

        lines.append(f"theory: {theory}")
        if defs:
            names = ", ".join(e["name"] for e in defs)
            lines.append(f"  definitions: {names}")
        if hyps:
            lines.append("  hypotheses / conjectures (realistic):")
            for e in hyps:
                tag = "HYP" if e["kind"] == "hypothesis" else "CONJ"
                lines.append(f"    [{tag}] {e['name']} : {e['detail']}")
        if thms:
            lines.append("  theorems:")
            for e in thms:
                status, note = _theorem_status(checker, e["name"])
                lines.append(f"    [{status}] {e['name']}   ({note})")
        if tests:
            lines.append("  tests:")
            for e in tests:
                tag = {"passed": "PASS", "failed": "FAIL", "ran": "RAN"}[e["status"]]
                extra = "" if e["status"] != "failed" else f"  ({e['detail']})"
                lines.append(f"    [{tag}] {e['name']}{extra}")
        if errs:
            lines.append("  errors:")
            for e in errs:
                lines.append(f"    [ERROR] {e['name']}: {e['detail']}")
        lines.append("")

    # summary
    proven = [n for n in checker.proven]
    certified = [n for n in proven if not (checker.cond_deps.get(n) or set())]
    conditional = [n for n in proven if (checker.cond_deps.get(n) or set())]
    open_thms = [n for n in checker.obligations if n not in checker.proven]
    tests_all = [e for evs in theories.values() for e in evs if e["kind"] == "test"]
    tpass = sum(1 for e in tests_all if e["status"] == "passed")
    tfail = sum(1 for e in tests_all if e["status"] == "failed")
    tran = sum(1 for e in tests_all if e["status"] == "ran")

    lines += [DASH, " Summary"]
    lines.append(f"   theorems   : {len(proven)} proven "
                 f"({len(certified)} certified, {len(conditional)} conditional), "
                 f"{len(open_thms)} open")
    lines.append(f"   conjectures: {len(checker.assumptions)} (realistic)")
    lines.append(f"   tests      : {tpass} passed, {tfail} failed, {tran} ran")
    ok = checker.failures == 0
    lines.append(f"   status     : {'OK' if ok else 'FAILURES'}  "
                 f"(exit {0 if ok else 1})")
    lines.append(DASH)
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Archive + scaffold
# --------------------------------------------------------------------------
def pack(directory, out=None):
    """Pack a project directory into a single .matyos archive."""
    directory = os.path.normpath(directory)
    if out is None:
        out = os.path.basename(directory) + ".matyos"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, _, filenames in os.walk(directory):
            for fn in filenames:
                ap = os.path.join(dirpath, fn)
                rel = os.path.relpath(ap, directory)
                z.write(ap, rel)
    return out


def unpack(archive, dest=None):
    """Extract a .matyos archive into a directory."""
    if dest is None:
        dest = os.path.splitext(os.path.basename(archive))[0]
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        z.extractall(dest)
    return dest


_SCAFFOLD = {
    "theories/arithmetic/defs.elk":
        "-- Shared vocabulary for the arithmetic theory.\n"
        "inductive Nat : Type :=\n"
        "  | zero : Nat\n"
        "  | succ : Nat -> Nat\n\n"
        "def add (m : Nat) (n : Nat) : Nat :=\n"
        "  Nat.rec (fun (_ : Nat) => Nat) n (fun (k : Nat) (ih : Nat) => succ ih) m\n\n"
        "def cong (A : Type) (B : Type) (f : A -> B) (a : A) (b : A) (e : Eq A a b)\n"
        "    : Eq B (f a) (f b) :=\n"
        "  Eq.J A a (fun (x : A) (_ : Eq A a x) => Eq B (f a) (f x)) (refl B (f a)) b e\n",

    "theories/arithmetic/conjectures.hyp":
        "-- An open conjecture: addition is commutative. We have NOT proved it,\n"
        "-- so anything depending on it is `realistic` (conditional).\n"
        "conjecture add_comm :\n"
        "  forall (a : Nat), forall (b : Nat), Eq Nat (add a b) (add b a)\n",

    "theories/arithmetic/nat.thm":
        "-- The proposition we aim to establish.\n"
        "theorem add_zero_right : forall (n : Nat), Eq Nat (add n zero) n\n",

    "theories/arithmetic/nat.test":
        "-- Computational experiments (the kernel runs them).\n"
        "test add_2_3 :\n"
        "  add (succ (succ zero)) (succ (succ (succ zero)))\n"
        "  = succ (succ (succ (succ (succ zero))))\n"
        "test add_0_4 :\n"
        "  add zero (succ (succ (succ (succ zero))))\n"
        "  = succ (succ (succ (succ zero)))\n",

    "theories/arithmetic/nat.prf":
        "-- The proof: induction on n, congruence on the successor.\n"
        "proof add_zero_right :=\n"
        "  fun (n : Nat) =>\n"
        "    Nat.rec (fun (m : Nat) => Eq Nat (add m zero) m)\n"
        "            (refl Nat zero)\n"
        "            (fun (k : Nat) (ih : Eq Nat (add k zero) k) =>\n"
        "                cong Nat Nat succ (add k zero) k ih)\n"
        "            n\n",

    "matyos.toml":
        "# MatyOS project manifest\n"
        'name = "{name}"\n'
        'version = "0.1.0"\n',
}


def scaffold(name):
    """Create a new project directory `name` with a sample theory."""
    if os.path.exists(name):
        raise FileExistsError(f"'{name}' already exists")
    for rel, content in _SCAFFOLD.items():
        dest = os.path.join(name, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(content.replace("{name}", name))
    return name
