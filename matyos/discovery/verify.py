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


# A deliberately tiny stand-in for OEIS: prefix -> known identifier/name.
# STUB: the real component queries OEIS and the literature over the network.
_LOCAL_OEIS: dict[tuple[int, ...], str] = {
    (0, 1, 1, 2, 3, 5, 8, 13): "A000045 (Fibonacci numbers)",
    (1, 1, 2, 3, 5, 8, 13, 21): "A000045 (Fibonacci numbers, offset)",
    (1, 2, 4, 8, 16, 32): "A000079 (powers of 2)",
    (0, 1, 3, 6, 10, 15): "A000217 (triangular numbers)",
}


def verify(obj: MathObject) -> Verification:
    notes: list[str] = []
    confirmed = _high_precision_confirm(obj, notes)
    art = _prior_art(obj)
    if art:
        notes.append(f"prior art: {art}")
    return Verification(confirmed=confirmed, prior_art=art, notes=notes)


def _high_precision_confirm(obj: MathObject, notes: list[str]) -> bool:
    """Re-run the numerical-anomaly check on a longer prefix, if we can extend it.

    For a formula we can generate more terms and confirm the match strengthens. For
    a bare sequence prefix we cannot extend it, so a match is reported as
    unconfirmed (short-prefix) rather than confirmed.
    """
    if isinstance(obj, Formula):
        long_terms = obj.evaluate_prefix(60)
        long_seq = Sequence(provenance=obj.provenance, terms=long_terms)
        s = scorer.score(long_seq)
        if s.breakdown.get("numerical_anomaly", 0.0) >= 1.0:
            notes.append("high-precision confirm: constant match holds on 60-term prefix")
            return True
        notes.append("high-precision confirm: match did not survive longer prefix")
        return False
    if isinstance(obj, Sequence):
        s = scorer.score(obj)
        if s.breakdown.get("numerical_anomaly", 0.0) >= 1.0:
            notes.append("constant match on given prefix (unconfirmed: cannot extend a bare sequence)")
        return False
    return False


def _prior_art(obj: MathObject) -> str | None:
    if isinstance(obj, Sequence):
        ints = _as_ints(obj.terms)
        if ints is not None:
            for prefix, name in _LOCAL_OEIS.items():
                if _startswith(ints, prefix) or _startswith(prefix, ints):
                    return name
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
