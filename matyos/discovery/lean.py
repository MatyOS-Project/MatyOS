"""Hand a discovery to Lean + mathlib — the honest way.

The point of connecting to Lean is *not* to re-prove mathematics in MatyOS, and
*not* to pretend an LLM-free autoformalizer is solved. It is to turn a discovered
numeric claim into a **Lean 4 theorem statement** a human (or a prover) can check
against **mathlib**, and to say whether a Lean toolchain is even available.

So this emits a statement with a `sorry` — matching the find's honest label
(REALISTIC / unproven) — never a finished proof. Proving it is Lean+mathlib's
job, not MatyOS's; MatyOS supplies the conjecture and the rigor around it.
"""

from __future__ import annotations

import re
import shutil


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
    if "closed form found" not in cf:
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
