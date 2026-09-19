"""Hand a discovery to Lean + mathlib — the honest way.

The point of connecting to Lean is *not* to re-prove mathematics in MatyOS, and
*not* to pretend an LLM-free autoformalizer is solved. It is to turn a discovered
numeric claim into a **Lean 4 theorem statement** a human (or a prover) can check
against **mathlib** — and, when a Lean toolchain is present, to *try to close it
automatically* with mathlib's proof automation.

`lean_statement` emits the statement with a `sorry` (matching the honest label:
REALISTIC / unproven). `try_prove` then swaps the `sorry` for each entry of a
ladder — single tactics (`rfl`, `decide`, `norm_num`, `simp_all`, `omega`,
`positivity`, `linarith`, `nlinarith`, `ring`, `tauto`, `aesop`), then multi-step
scripts, then `exact?` (mathlib lemma search, which reports the lemma it used) —
runs Lean against mathlib, and keeps the first that compiles with no errors and no
`sorry`. Results are cached; the closing tactic and any lemma are recorded. That
closes *easy* goals only — simple identities, decidable facts, one-lemma hits. A
hard or general conjecture returns `open`, honestly, for a human. MatyOS never
reports `proved` unless Lean itself accepted the proof; it never fabricates one.
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


# MatyOS graph invariant -> (mathlib expression over `G`, value type). Only those
# with a confirmed mathlib definition are listed; everything else has no mathlib
# counterpart yet and is emitted as an honest placeholder.
_GRAPH_LEAN = {
    "radius": ("G.radius", "ℕ∞"),
    "diameter": ("G.ediam", "ℕ∞"),          # ediam is the ℕ∞-valued diameter
    "clique_number": ("G.cliqueNum", "ℕ"),
    "chromatic_number": ("G.chromaticNumber", "ℕ∞"),
    "order": ("(Fintype.card V)", "ℕ"),
}


def graph_statement(text: str) -> dict:
    """Emit a Lean 4 statement for a graph-invariant inequality ``"A <= B"``.

    Returns {lean_statement, mathlib_ready, note}. ``mathlib_ready`` is True only
    when *both* invariants have a mathlib definition of the *same* value type, so
    the statement can actually be checked/attempted; otherwise a clearly-labelled
    skeleton is emitted (invariants absent from mathlib appear as `MatyOS.<name> G`
    placeholders that a human/future work must define). Honest: MatyOS states the
    conjecture; it does not assert the statement typechecks unless mathlib_ready.
    """
    if " <= " not in text:
        return {"lean_statement": None, "mathlib_ready": False,
                "note": f"unparseable inequality: {text!r}"}
    a, b = text.split(" <= ", 1)
    A, B = _GRAPH_LEAN.get(a), _GRAPH_LEAN.get(b)
    header = ("import Mathlib\n\n"
              "-- MatyOS graph conjecture (unproven; holds on the sampled graphs).\n")
    # [Nonempty V] is needed for many mathlib graph-metric lemmas (radius/ediam are
    # ⊤ on the empty graph); [DecidableEq V] helps decidability-based tactics.
    var = ("{V : Type*} [Fintype V] [Nonempty V] [DecidableEq V] "
           "(G : SimpleGraph V) [DecidableRel G.Adj]")
    if A and B and A[1] == B[1]:
        stmt = (f"{header}-- both invariants map to mathlib ({A[1]}).\n"
                f"theorem matyos_graph_conjecture {var} :\n"
                f"    {A[0]} ≤ {B[0]} := by\n  sorry\n")
        return {"lean_statement": stmt, "mathlib_ready": True,
                "note": "both invariants are in mathlib; a candidate for try_prove"}
    ax = A[0] if A else f"MatyOS.{a} G"
    bx = B[0] if B else f"MatyOS.{b} G"
    missing = [n for n, m in ((a, A), (b, B)) if not m]
    why = ("invariants not in mathlib (need defining): " + ", ".join(missing)) if missing \
        else "invariants have different mathlib value types (coercion needed)"
    stmt = (f"{header}-- {why}.\n"
            f"theorem matyos_graph_conjecture {var} :\n"
            f"    {ax} ≤ {bx} := by\n  sorry\n")
    return {"lean_statement": stmt, "mathlib_ready": False, "note": why}


# ---- the proving leg: try to close a statement with mathlib automation --------

# Single tactics, cheap→strong. `exact?` is mathlib *lemma search*: it closes the
# goal from the library if it can, and reports the lemma it used (captured below).
_SINGLE_TACTICS = [
    "rfl", "decide", "norm_num", "simp_all", "omega", "positivity",
    "linarith", "nlinarith", "ring", "tauto", "aesop", "exact?",
]

# Multi-step scripts: many goals need an intro/constructor before automation bites.
_TACTIC_SEQUENCES = [
    "intro _ <;> simp_all",
    "intros <;> omega",
    "constructor <;> simp_all",
    "simp only [] <;> ring",
    "norm_num <;> nlinarith",
]

_TACTIC_LADDER = _SINGLE_TACTICS + _TACTIC_SEQUENCES

# Proof cache: identical (statement, ladder) pairs should not re-invoke Lean. Keyed
# by a hash; kept in memory, and persisted to MATYOS_PROOF_CACHE (JSON) when set.
_PROOF_CACHE: dict[str, dict] = {}
_CACHE_LOADED = False


def _cache_key(statement: str, ladder: list[str]) -> str:
    import hashlib
    return hashlib.sha256((" ".join(ladder) + "\n" + statement).encode()).hexdigest()


def _ensure_cache_loaded() -> None:
    global _CACHE_LOADED
    if _CACHE_LOADED:
        return
    _CACHE_LOADED = True
    p = os.environ.get("MATYOS_PROOF_CACHE")
    if p and os.path.exists(p):
        try:
            import json
            with open(p, encoding="utf-8") as f:
                _PROOF_CACHE.update(json.load(f))
        except Exception:                        # a corrupt cache must never break proving
            pass


def _cache_put(key: str, result: dict) -> None:
    stored = {k: v for k, v in result.items() if k != "from_cache"}
    _PROOF_CACHE[key] = stored
    p = os.environ.get("MATYOS_PROOF_CACHE")
    if p:
        try:
            import json
            with open(p, "w", encoding="utf-8") as f:
                json.dump(_PROOF_CACHE, f)
        except Exception:
            pass


def _extract_lemma(log: str) -> str | None:
    """Pull the lemma `exact?`/`apply?` suggests from Lean's "Try this:" message.

    The suggestion may be on the same line or the next, and may carry a bracketed
    tag, e.g.  `Try this:\\n  [apply] exact Nat.add_comm a b`. Take the first
    non-empty text after the marker and strip any leading `[...]` tag.
    """
    idx = log.find("Try this:")
    if idx == -1:
        return None
    rest = log[idx + len("Try this:"):].strip()
    if not rest:
        return None
    first = rest.splitlines()[0].strip()
    first = re.sub(r"^\[[^\]]*\]\s*", "", first)      # drop a leading [apply]/[exact] tag
    return first or None


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


def try_prove(statement: str, timeout: int = 120, tactics=None,
              use_cache: bool = True) -> dict:
    """Try to close a MatyOS Lean statement automatically with mathlib.

    Replaces the `sorry` with each entry of the ladder (single tactics, then
    multi-step scripts, then `exact?` mathlib lemma search), runs Lean, and returns
    the first that compiles clean. Honest statuses, never a fabricated proof:

    - ``proved``              — Lean accepted it; ``tactic`` is the closing entry and
                                ``lemma`` names the mathlib lemma when `exact?`/
                                `apply?` found one.
    - ``open``                — nothing in the ladder closed it; a human/real proof
                                is needed. ``attempts`` lists what was tried.
    - ``lean_unavailable``    — no `lean` on PATH (install elan/Lean 4).
    - ``mathlib_unavailable`` — statement needs mathlib but no project configured
                                (set MATYOS_LEAN_PROJECT to a built lake project).
    - ``error``               — nothing to close, or Lean could not be invoked.

    Results are cached by (statement, ladder); a cache hit sets ``from_cache``.
    Set ``MATYOS_PROOF_CACHE`` to a path to persist the cache across runs.
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
    key = _cache_key(statement, ladder)
    if use_cache:
        _ensure_cache_loaded()
        if key in _PROOF_CACHE:
            hit = dict(_PROOF_CACHE[key])
            hit["from_cache"] = True
            return hit
    attempts: list[dict] = []
    for tac in ladder:
        source = statement.replace("sorry", tac)
        ok, log = _run_lean(source, project, timeout)
        attempts.append({"tactic": tac, "ok": ok})
        if ok:
            lemma = _extract_lemma(log) if tac in ("exact?", "apply?") else None
            result = {"status": "proved", "proved": True, "tactic": tac,
                      "lemma": lemma, "attempts": attempts, "from_cache": False,
                      "note": f"proved via {lemma}" if lemma else f"proved by `{tac}`"}
            if use_cache:
                _cache_put(key, result)
            return result
    result = {"status": "open", "proved": False, "tactic": None,
              "attempts": attempts, "from_cache": False,
              "note": "no tactic or mathlib lemma in the ladder closed it; "
                      "a human/real proof is needed"}
    if use_cache:
        _cache_put(key, result)
    return result
