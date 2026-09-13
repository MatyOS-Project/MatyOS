"""Interestingness Scorer.

The hardest and most important component. Full automation of "interesting" is an
open problem industry-wide — that is precisely Terence Tao's point about AI-for-math
— so this module does **not** try to be a judge. It computes a handful of concrete,
reproducible *proxies* and returns them as a breakdown, so a human triages a short
ranked list rather than trusting a single opaque number.

Proxies implemented:

- ``numerical_anomaly`` — does a characteristic number of the object land on a
  known mathematical constant? (real, via high-precision matching)
- ``structural_novelty``  — is the object irreducible to a trivially simpler one?
  (crude proxy)
- ``resonance``           — cross-domain resonance: did this object arrive by a
  cross-domain transfer that survived? (real signal from provenance)
- ``surprise``            — deviation from a random-baseline null model (crude proxy)

Each proxy returns a float in ``[0, 1]``. ``score`` combines them, but the caller
should read the breakdown, not just the total.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, getcontext
from fractions import Fraction

from matyos.discovery.objects import MathObject, Sequence, Formula, Series
from matyos.discovery import anomaly

getcontext().prec = 50

# Known constants, to enough precision for the toy matcher. Value -> name.
_KNOWN_CONSTANTS: dict[str, Decimal] = {
    "phi (golden ratio)": (Decimal(1) + Decimal(5).sqrt()) / Decimal(2),
    "pi": Decimal("3.14159265358979323846264338327950288419716939937510"),
    "e": Decimal("2.71828182845904523536028747135266249775724709369995"),
    "sqrt(2)": Decimal(2).sqrt(),
    "euler-mascheroni gamma": Decimal("0.57721566490153286060651209008240243104215933593992"),
}

_MATCH_TOLERANCE = Decimal("1e-6")


@dataclass(frozen=True)
class Score:
    total: float
    breakdown: dict[str, float]
    notes: dict[str, str]


def score(obj: MathObject) -> Score:
    breakdown: dict[str, float] = {}
    notes: dict[str, str] = {}

    anomaly, anomaly_note = _numerical_anomaly(obj)
    breakdown["numerical_anomaly"] = anomaly
    if anomaly_note:
        notes["numerical_anomaly"] = anomaly_note

    mystery = _mystery(obj)
    breakdown["mystery"] = mystery
    if mystery >= 1.0:
        notes["mystery"] = ("stable constant with no known closed form — "
                            "the interesting kind; worth a human look")

    breakdown["structural_novelty"] = _structural_novelty(obj)
    breakdown["resonance"] = _resonance(obj)
    breakdown["surprise"] = _surprise(obj)

    # Weighted sum. A recognised closed form (anomaly) and cross-domain resonance
    # are the strongest signals; a *mystery* — a real constant we cannot yet name —
    # is weighted right alongside them, because unknown constants are exactly where
    # new discoveries hide. Novelty and surprise stay crude, weighted down.
    weights = {"numerical_anomaly": 0.35, "resonance": 0.25, "mystery": 0.25,
               "structural_novelty": 0.1, "surprise": 0.05}
    total = sum(breakdown[k] * w for k, w in weights.items())
    return Score(total=total, breakdown=breakdown, notes=notes)


def _characteristic_ratio_exact(obj: MathObject) -> Fraction | None:
    """Exact limiting ratio of consecutive terms, or None if it doesn't settle.

    For a Formula we generate a long prefix (exact Fractions), so the ratio is
    known to very high precision — what PSLQ needs. For a bare Sequence we can
    only use the terms we have.
    """
    if isinstance(obj, Formula):
        terms = obj.evaluate_prefix(160)
    elif isinstance(obj, Sequence):
        terms = obj.terms
    else:
        return None
    ratios = [t / s for s, t in zip(terms, terms[1:]) if s != 0]
    if len(ratios) < 4:
        return None
    lo, hi = min(ratios[-3:]), max(ratios[-3:])
    if hi - lo > Fraction(1, 10 ** 4):
        return None
    return ratios[-1]


def _mystery(obj: MathObject) -> float:
    """1.0 if this is a series that converges to a *stable* constant with NO known
    closed form — an unexplained constant, the interesting kind. Requires the
    value to agree at two precisions (so it's a real limit, not numerical noise).
    """
    if not isinstance(obj, Series) or not anomaly.HAVE_PSLQ:
        return 0.0
    val = obj.value(80)
    if val is None:
        return 0.0
    if anomaly.find_closed_form(val, dps=80) is not None:
        return 0.0                       # explained — not a mystery
    try:
        import mpmath as mp
        val2 = obj.value(110)
        if val2 is not None and abs(val - val2) < mp.mpf(10) ** (-40):
            return 1.0                   # stable constant, unnamed
    except Exception:
        return 0.0
    return 0.0


def _numerical_anomaly(obj: MathObject) -> tuple[float, str]:
    """1.0 if the object's characteristic number has a closed form, else 0.0.

    The real signal, in the spirit of the Ramanujan Machine: run PSLQ
    (:mod:`matyos.discovery.anomaly`) to search for an integer relation against a
    basis of constants. If mpmath is unavailable we fall back to matching a small
    table of known constants.
    """
    # Series: the characteristic quantity is the sum's value, not a ratio.
    if isinstance(obj, Series):
        if not anomaly.HAVE_PSLQ:
            return 0.0, ""
        val = obj.value(80)
        if val is None:
            return 0.0, ""
        rel = anomaly.find_closed_form(val, dps=80)
        if rel is not None:
            return 1.0, f"closed form found (PSLQ): sum = {rel.formula[4:]}"
        return 0.0, f"sum ~{float(val):.10f} (no known closed form — mystery constant)"

    ratio = _characteristic_ratio_exact(obj)
    if ratio is None:
        return 0.0, ""
    if anomaly.HAVE_PSLQ:
        rel = anomaly.find_closed_form(ratio)
        if rel is not None:
            return 1.0, f"closed form found (PSLQ): {rel.formula}"
        return 0.0, f"ratio ~{float(ratio):.10f} (no closed form found)"
    # Fallback: coarse known-constant table.
    x = Decimal(ratio.numerator) / Decimal(ratio.denominator)
    for name, value in _KNOWN_CONSTANTS.items():
        if abs(x - value) < _MATCH_TOLERANCE:
            return 1.0, f"characteristic number {x:.10f} matches {name} (no PSLQ; install mpmath)"
    return 0.0, f"characteristic number {x:.10f} (no match; install mpmath for PSLQ)"


def _structural_novelty(obj: MathObject) -> float:
    """Crude proxy: penalise objects that are trivially constant or arithmetic.

    A real novelty measure would ask whether the object factors through a known
    simpler construction. Here we only reject the obviously boring.
    """
    if isinstance(obj, Sequence) and len(obj.terms) >= 3:
        diffs = {b - a for a, b in zip(obj.terms, obj.terms[1:])}
        if len(diffs) == 1:            # constant or arithmetic progression
            return 0.1
    return 0.6


def _resonance(obj: MathObject) -> float:
    """Cross-domain resonance signal, read from provenance.

    An object that arrived via a cross-domain transfer *and* survived generation
    carries resonance: a structure that meant something in another domain re-formed
    here. This is a real (if minimal) reading of the differentiator mechanic.
    """
    return 1.0 if obj.provenance.startswith("transfer:") else 0.0


def _surprise(obj: MathObject) -> float:
    """STUB-ish: deviation from a random-baseline null model.

    Placeholder proxy — returns a mild constant. A real implementation compares the
    object against a null distribution of random objects of the same shape and
    scores how far into the tail it sits.
    """
    return 0.5
