"""Hand a discovery to Lean + mathlib — the honest way.

The point of connecting to Lean is *not* to re-prove mathematics in MatyOS, and
*not* to pretend an LLM-free autoformalizer is solved. It is to turn a discovered
numeric claim into a **Lean 4 theorem statement** a human (or a prover) can check
against **mathlib** — and, when a Lean toolchain is present, to *try to close it
automatically* with mathlib's proof automation.

`lean_statement` emits the statement with a `sorry` (matching the honest label:
REALISTIC / unproven). `try_prove` then swaps the `sorry` for each tactic in a
ladder (`decide`, `norm_num`, `nlinarith`, `polyrith`, `simp`, `aesop`), runs Lean
against mathlib, and keeps the first that compiles with no errors and no `sorry`.
That closes *easy* goals only — simple identities, decidable finite facts. A hard
or general conjecture returns `open`, honestly, for a human. MatyOS never reports
`proved` unless Lean itself accepted the proof; it never fabricates one.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile


def toolchain() -> dict:
    """Report which Lean tools are on PATH (lean, lake)."""
    return {
        "lean": shutil.which("lean") is not None,
        "lake": shutil.which("lake") is not None,
        "ready": shutil.which("lean") is not None,
    }


_LEAN_CONSTS = {
    "sqrt2": "Real.sqrt 2", "sqrt3": "Real.sqrt 3", "sqrt5": "Real.sqrt 5",
    "pi": "Real.pi", "ln2": "Real.log 2",
    "gamma": "eulerMascheroniConstant", "e": "Real.exp 1",
}


def _to_lean_expr(rhs: str) -> str:
    """Render a MatyOS closed-form RHS (e.g. "(1 + sqrt5) / 2", "(pi^2) / 6")
    into Lean/mathlib notation, in a single token pass so inserted text is never
    re-substituted (naive chained replaces turn the 'e' inside 'Real' into junk).
    """
    return re.sub(r"[A-Za-z]+[0-9]*",
                  lambda m: _LEAN_CONSTS.get(m.group(0), m.group(0)), rhs)


def _rhs_of(closed_form: str) -> str:
    body = closed_form.split(":", 1)[1].strip()      # "sum = (pi^2) / 6" / "x = ..."
    return body.split("=", 1)[1].strip() if "=" in body else body


def lean_statement(record: dict) -> str | None:
    """Emit a Lean 4 theorem statement (with `sorry`) for a discovered find.

    Returns None when the find has no closed form to state. The LHS is described
    from the object; a Series maps cleanly to mathlib's `∑'`. Other domains get a
    templated LHS the reader must complete — MatyOS is honest that it is stating,
    not proving.
    """
    cf = record.get("closed_form", "")
    if "(PSLQ):" not in cf:          # a real hit; not "(no closed form found)"
        return None
    rhs = _to_lean_expr(_rhs_of(cf))
    disp = record.get("display", {})
    kind = disp.get("kind")
    header = ("-- MatyOS discovery → Lean statement (unproven).\n"
              "-- Verify in a project with `import Mathlib`. Replace `sorry` with a proof.\n"
              "import Mathlib\n\n")
    if kind == "series":
        lhs_note = disp.get("text", "the series")
        return (header +
                f"-- LHS is {lhs_note}; confirm the exact term against the object.\n"
                f"theorem matyos_discovery : (∑' n : ℕ, (term n : ℝ)) = {rhs} := by\n  sorry\n")
    if kind == "formula":
        return (header +
                f"-- The dominant-root / limiting ratio of {disp.get('text','the recurrence')}.\n"
                f"theorem matyos_discovery : limitingRatio = {rhs} := by\n  sorry\n")
    return header + f"theorem matyos_discovery : x = {rhs} := by\n  sorry\n"


# ---- the proving leg: try to close a statement with mathlib automation --------

_TACTIC_LADDER = ["decide", "norm_num", "nlinarith", "polyrith", "simp", "aesop"]


def _mathlib_project() -> str | None:
    """A lake project (with mathlib built) to run goals in, from the environment.

    `import Mathlib` only resolves inside such a project, so proving real number
    facts needs one. Point MATYOS_LEAN_PROJECT at it; None means 'not configured'.
    """
    p = os.environ.get("MATYOS_LEAN_PROJECT")
    return p if p and os.path.isdir(p) else None


def _run_lean(source: str, project: str | None, timeout: int) -> tuple[bool, str]:
    """Compile a Lean source string; True iff it builds clean (no error, no sorry).

    Inside a mathlib project we invoke `lake env lean` so the mathlib search path
    is set; otherwise bare `lean` (only mathlib-free goals can pass that way).
    """
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "Matyos_goal.lean")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(source)
        cmd = (["lake", "env", "lean", f] if project else ["lean", f])
        try:
            r = subprocess.run(cmd, cwd=project, capture_output=True, text=True,
                               timeout=timeout)
        except subprocess.TimeoutExpired:
            return False, "timeout"
        except OSError as e:
            return False, f"could not run Lean: {e}"
        log = (r.stdout + r.stderr)
        clean = (r.returncode == 0 and "error" not in r.stderr.lower()
                 and "sorry" not in log.lower())
        return clean, log[-2000:]


def try_prove(statement: str, timeout: int = 120, tactics=None) -> dict:
    """Try to close a MatyOS Lean statement automatically with mathlib tactics.

    Replaces the `sorry` with each tactic in the ladder, runs Lean, and returns
    the first that compiles clean. Honest statuses, never a fabricated proof:

    - ``proved``              — Lean accepted it; the closing ``tactic`` is named.
    - ``open``                — no tactic closed it; a human/real proof is needed.
    - ``lean_unavailable``    — no `lean` on PATH (install elan/Lean 4).
    - ``mathlib_unavailable`` — statement needs mathlib but no project configured
                                (set MATYOS_LEAN_PROJECT to a built lake project).
    - ``error``               — nothing to close, or Lean could not be invoked.
    """
    tc = toolchain()
    if not tc["lean"]:
        return {"status": "lean_unavailable", "proved": False,
                "note": "no `lean` on PATH; install Lean 4 (elan) to enable proving"}
    if "sorry" not in statement:
        return {"status": "error", "proved": False,
                "note": "statement has no `sorry` to close"}
    project = _mathlib_project()
    if "import Mathlib" in statement and project is None:
        return {"status": "mathlib_unavailable", "proved": False,
                "note": "goal needs mathlib; set MATYOS_LEAN_PROJECT to a lake "
                        "project with mathlib built"}
    ladder = list(tactics or _TACTIC_LADDER)
    for tac in ladder:
        source = statement.replace("sorry", tac)
        ok, _log = _run_lean(source, project, timeout)
        if ok:
            return {"status": "proved", "proved": True, "tactic": tac}
    return {"status": "open", "proved": False, "tried": ladder,
            "note": "no automation tactic closed it; a human/real proof is needed"}
