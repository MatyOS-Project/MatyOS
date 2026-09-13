"""Cheap verification.

Before anything is surfaced as a candidate discovery it passes a few cheap checks.
The point is triage, not proof: catch the obviously-known and the obviously-wrong so
a human only looks at a short, plausible list.

Checks:

- ``high_precision_confirm`` — recompute the object's characteristic number from a
  longer prefix and confirm the constant match still holds (guards against a match
  that was a short-prefix coincidence). Real.
- ``prior_art`` — is this a known sequence? Offline OEIS-style lookup against a tiny
  local table. STUB for the real (networked) OEIS / literature search.
- ``formal_handoff`` — optional export to a proof assistant. STUB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction

from matyos.discovery.objects import MathObject, Sequence, Formula, Series
from matyos.discovery import scorer


@dataclass(frozen=True)
class Verification:
    confirmed: bool
    prior_art: str | None
    notes: list[str] = field(default_factory=list)
    refutation: str = "n/a"          # survived / refuted / n/a
    label: dict = field(default_factory=dict)


import json
import urllib.parse
import urllib.request

# Offline fallback used when the OEIS API is unreachable.
_LOCAL_OEIS: dict[tuple[int, ...], str] = {
    (0, 1, 1, 2, 3, 5, 8, 13): "A000045 (Fibonacci numbers)",
    (1, 1, 2, 3, 5, 8, 13, 21): "A000045 (Fibonacci numbers, offset)",
    (1, 2, 4, 8, 16, 32): "A000079 (powers of 2)",
    (0, 1, 3, 6, 10, 15): "A000217 (triangular numbers)",
}

_OEIS_URL = "https://oeis.org/search"
_OEIS_UA = {"User-Agent": "MatyOS-discovery/0.1"}


def oeis_lookup(ints: tuple[int, ...], timeout: float = 8.0) -> tuple[str | None, bool]:
    """Look a sequence up in OEIS. Returns (identifier_or_None, was_live).

    Tries the live OEIS API first (it returns a JSON list of matches); on any
    network failure it falls back to the small local table, so the engine still
    runs offline. ``was_live`` says which path answered.
    """
    if len(ints) >= 4:
        q = ",".join(str(n) for n in ints)
        url = f"{_OEIS_URL}?{urllib.parse.urlencode({'q': q, 'fmt': 'json'})}"
        try:
            req = urllib.request.Request(url, headers=_OEIS_UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.load(resp)
            # OEIS returns a JSON list of matches, or literal `null` for no match.
            if isinstance(data, list):
                results = data
            elif isinstance(data, dict):
                results = data.get("results") or []
            else:
                results = []
            if results:
                r = results[0]
                name = r.get("name", "")
                return f"A{int(r['number']):06d} ({name[:60]})", True
            return None, True  # live answer: genuinely not in OEIS
        except Exception:
            pass  # fall through to offline table
    for prefix, name in _LOCAL_OEIS.items():
        if _startswith(ints, prefix) or _startswith(prefix, ints):
            return name, False
    return None, False


def verify(obj: MathObject) -> Verification:
    from matyos.discovery.label import realistic_label
    notes: list[str] = []
    confirmed = _high_precision_confirm(obj, notes)
    verdict, rnote = refute(obj)
    if rnote:
        notes.append(rnote)
    art = _prior_art(obj, notes)
    has_cf = verdict != "n/a" or confirmed
    is_mystery = scorer.score(obj).breakdown.get("mystery", 0.0) >= 1.0
    if is_mystery:
        notes.append("mystery: a stable constant with no known closed form — worth a human look")
    label = realistic_label(has_closed_form=has_cf, refutation=verdict,
                            prior_art=art, is_mystery=is_mystery)
    return Verification(confirmed=confirmed, prior_art=art, notes=notes,
                        refutation=verdict, label=label)


def _high_precision_confirm(obj: MathObject, notes: list[str]) -> bool:
    """Independently re-derive the closed form from a much longer prefix.

    A formula can be extended, so we recompute its ratio from a far longer prefix
    and confirm the same closed form is found — guarding against a match that was
    a short-prefix coincidence. A bare sequence cannot be extended, so a match on
    it is reported as unconfirmed.
    """
    from matyos.discovery import anomaly
    if isinstance(obj, Series):
        val = obj.value(60)
        if val is not None and anomaly.HAVE_PSLQ:
            rel = anomaly.find_closed_form(val, dps=60)
            if rel is not None:
                notes.append(f"high-precision confirm: sum = {rel.formula[4:]} holds at 60 digits")
                return True
        notes.append("high-precision confirm: no closed form at higher precision")
        return False
    if isinstance(obj, Formula):
        terms = obj.evaluate_prefix(300)
        ratios = [t / s for s, t in zip(terms, terms[1:]) if s != 0]
        if len(ratios) >= 4 and anomaly.HAVE_PSLQ:
            rel = anomaly.find_closed_form(ratios[-1])
            if rel is not None:
                notes.append(f"high-precision confirm: {rel.formula} holds on a 300-term prefix")
                return True
        notes.append("high-precision confirm: no closed form on the longer prefix")
        return False
    if isinstance(obj, Sequence):
        s = scorer.score(obj)
        if s.breakdown.get("numerical_anomaly", 0.0) >= 1.0:
            notes.append("closed form on given prefix (unconfirmed: cannot extend a bare sequence)")
        return False
    return False


def refute(obj: MathObject) -> tuple[str, str]:
    """Actively try to break a discovered closed form (falsification).

    Derive the closed form from a near window, then predict the invariant far
    beyond it and check the prediction holds. A short-prefix coincidence fails
    here; a genuine law survives. Returns (verdict, note) where verdict is one of
    "survived", "refuted", or "n/a" (nothing falsifiable — no closed form).
    """
    from matyos.discovery import anomaly
    if isinstance(obj, Series) and anomaly.HAVE_PSLQ:
        v1, v2 = obj.value(50), obj.value(72)
        if v1 is None:
            return "n/a", ""
        r1 = anomaly.find_closed_form(v1, dps=50)
        if r1 is None:
            return "n/a", ""
        r2 = anomaly.find_closed_form(v2, dps=72)
        if r2 is not None and r2.formula == r1.formula:
            return "survived", f"refutation survived: sum = {r1.formula[4:]} stable to 72 digits"
        return "refuted", "refuted: the closed form did not survive higher precision"
    if not (isinstance(obj, Formula) and anomaly.HAVE_PSLQ):
        return "n/a", ""
    near = obj.evaluate_prefix(120)
    near_ratios = [t / s for s, t in zip(near, near[1:]) if s != 0]
    if len(near_ratios) < 4:
        return "n/a", ""
    rel = anomaly.find_closed_form(near_ratios[-1])
    if rel is None:
        return "n/a", ""
    far = obj.evaluate_prefix(400)
    far_ratio = far[-1] / far[-2]
    predicted = anomaly.value_of(rel)
    import mpmath as mp
    mp.mp.dps = 50
    actual = mp.mpf(far_ratio.numerator) / mp.mpf(far_ratio.denominator)
    if abs(actual - predicted) < mp.mpf(10) ** (-30):
        return "survived", f"refutation survived: {rel.formula} predicts n=400 to 30 digits"
    return "refuted", f"refuted: {rel.formula} fails at n=400 (predicted vs actual diverge)"


def _prior_art(obj: MathObject, notes: list[str]) -> str | None:
    if isinstance(obj, Series):
        # For a constant, matching known constants MEANS it is a known expression;
        # a sum with NO closed form is the interesting mystery (novel frontier).
        from matyos.discovery import anomaly
        val = obj.value(50) if anomaly.HAVE_PSLQ else None
        rel = anomaly.find_closed_form(val, dps=50) if val is not None else None
        if rel is not None:
            notes.append(f"prior art: expressible in known constants ({rel.formula[4:]})")
            return "known constant"
        notes.append("no prior art: sum has no closed form in the known-constant basis — a mystery constant")
        return None
    if isinstance(obj, Sequence):
        terms = obj.terms
    elif isinstance(obj, Formula):
        terms = obj.evaluate_prefix(12)   # the sequence this rule generates
    else:
        return None
    ints = _as_ints(terms)
    if ints is None:
        return None
    ident, live = oeis_lookup(ints)
    src = "OEIS live" if live else "offline table"
    if ident:
        notes.append(f"prior art [{src}]: {ident}")
        return ident
    notes.append(f"no prior art [{src}] — not a known sequence")
    return None


def _as_ints(terms: tuple[Fraction, ...]) -> tuple[int, ...] | None:
    out: list[int] = []
    for t in terms:
        if t.denominator != 1:
            return None
        out.append(t.numerator)
    return tuple(out)


def _startswith(a: tuple[int, ...], b: tuple[int, ...]) -> bool:
    n = min(len(a), len(b))
    return n >= 4 and a[:n] == b[:n]


# --- STUB ---

def formal_handoff(record: dict) -> dict:
    """Hand a discovery record to Lean: emit a theorem statement (with `sorry`)
    to verify against mathlib, and report whether a Lean toolchain is available.
    MatyOS states the conjecture; proving it is Lean+mathlib's job."""
    from matyos.discovery import lean
    return {
        "lean_statement": lean.lean_statement(record),
        "toolchain": lean.toolchain(),
        "note": "statement only (sorry) — MatyOS states, it does not prove",
    }
