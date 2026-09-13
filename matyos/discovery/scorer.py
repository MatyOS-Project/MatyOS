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

from matyos.discovery.objects import MathObject, Sequence, Formula

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

    breakdown["structural_novelty"] = _structural_novelty(obj)
    breakdown["resonance"] = _resonance(obj)
    breakdown["surprise"] = _surprise(obj)

    # Weighted sum. Anomaly and resonance are the signals we trust most in this
    # scaffold; novelty and surprise are crude and weighted down accordingly.
    weights = {"numerical_anomaly": 0.4, "resonance": 0.3,
               "structural_novelty": 0.15, "surprise": 0.15}
    total = sum(breakdown[k] * w for k, w in weights.items())
    return Score(total=total, breakdown=breakdown, notes=notes)


def _characteristic_number(obj: MathObject) -> Decimal | None:
    """Extract one real number that characterises the object, or None.

    For a sequence, the limiting ratio of consecutive terms (if it appears to
    settle). For a formula, the same, computed from a longer generated prefix.
    """
    terms: tuple[Fraction, ...]
    if isinstance(obj, Sequence):
        terms = obj.terms
    elif isinstance(obj, Formula):
        terms = obj.evaluate_prefix(40)
    else:
        return None

    ratios = [t / s for s, t in zip(terms, terms[1:]) if s != 0]
    if len(ratios) < 4:
        return None
    tail = ratios[-3:]
    # Require the last few ratios to agree to a few digits before we call it a limit.
    lo, hi = min(tail), max(tail)
    if hi - lo > Fraction(1, 10 ** 4):
        return None
    return Decimal(tail[-1].numerator) / Decimal(tail[-1].denominator)


def _numerical_anomaly(obj: MathObject) -> tuple[float, str]:
    """1.0 if a characteristic number matches a known constant, else 0.0.

    This is the only proxy that is fully real: it is a genuine (if narrow)
    high-precision constant match, in the spirit of the Ramanujan Machine. A real
    system would use PSLQ over a basis of constants; that is left as a STUB below.
    """
    x = _characteristic_number(obj)
    if x is None:
        return 0.0, ""
    for name, value in _KNOWN_CONSTANTS.items():
        if abs(x - value) < _MATCH_TOLERANCE:
            return 1.0, f"characteristic number {x:.10f} matches {name}"
    return 0.0, f"characteristic number {x:.10f} (no known-constant match)"


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


# --- STUBS: real interestingness machinery, deliberately not implemented here ---

def pslq_constant_match(_value: Decimal, _basis: list[Decimal]) -> None:
    """STUB. Integer-relation detection (PSLQ) of a value against a constant basis.

    The honest version of :func:`_numerical_anomaly`. Returns the integer relation
    if one exists. Not implemented in the scaffold.
    """
    raise NotImplementedError("PSLQ constant matching is a v2 TODO")
