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

from matyos.discovery.objects import MathObject, Sequence, Formula
from matyos.discovery import scorer


@dataclass(frozen=True)
class Verification:
    confirmed: bool
    prior_art: str | None
    notes: list[str] = field(default_factory=list)


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
            results = data if isinstance(data, list) else data.get("results") or []
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
    notes: list[str] = []
    confirmed = _high_precision_confirm(obj, notes)
    art = _prior_art(obj, notes)
    return Verification(confirmed=confirmed, prior_art=art, notes=notes)


def _high_precision_confirm(obj: MathObject, notes: list[str]) -> bool:
    """Independently re-derive the closed form from a much longer prefix.

    A formula can be extended, so we recompute its ratio from a far longer prefix
    and confirm the same closed form is found — guarding against a match that was
    a short-prefix coincidence. A bare sequence cannot be extended, so a match on
    it is reported as unconfirmed.
    """
    from matyos.discovery import anomaly
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


def _prior_art(obj: MathObject, notes: list[str]) -> str | None:
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

def formal_handoff(_obj: MathObject) -> None:
    """STUB. Export a candidate to a proof assistant (Lean, or MatyOS's own kernel)
    for an optional small proof attempt. Not implemented in the scaffold."""
    raise NotImplementedError("formal proof handoff is a v2 TODO")
