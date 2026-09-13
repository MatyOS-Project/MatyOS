"""Continued-fraction search — the Ramanujan-Machine move.

Enumerate simple polynomial continued fractions b0 + a1/(b1 + a2/(b2 + ...)),
compute each value to high precision, and hunt a closed form for the value (or
its reciprocal). A hit is a continued-fraction identity for a constant — the kind
of thing the Ramanujan Machine discovered.

The search is deliberately bounded (small integer polynomial coefficients, low
degree). It is a *candidate generator*: every hit still needs a human/proof, and
most bounded searches only rediscover known identities — but this is the one part
of MatyOS whose output could, in principle, be new.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from matyos.discovery.objects import ContinuedFraction
from matyos.discovery import anomaly


@dataclass(frozen=True)
class CFHit:
    text: str            # the continued fraction, described
    value: str           # decimal value
    closed_form: str     # e.g. "x = (pi) / 4"  (x is the value, or 1/value)
    reciprocal: bool     # whether the closed form is for 1/value


def _poly(coeffs):
    """Return a function n -> c0 + c1*n + c2*n^2 for the given integer coeffs."""
    return lambda n: sum(c * n ** i for i, c in enumerate(coeffs))


def search(coeff_range: int = 2, degree: int = 2, dps: int = 80,
           max_hits: int = 25, max_scan: int = 4000, terms: int = 150) -> list[CFHit]:
    """Scan polynomial continued fractions and return the identities found.

    coeff_range: integer coefficients range over -coeff_range..coeff_range.
    degree:      polynomial degree for a(n) and b(n).
    max_scan:    hard cap on continued fractions examined (this is a heavy search;
                 each one is a high-precision evaluation plus two PSLQ hunts).
    Returns at most ``max_hits`` CFHits. Requires mpmath.
    """
    if not anomaly.HAVE_PSLQ:
        return []
    hits: list[CFHit] = []
    seen: set[str] = set()
    scanned = 0
    rng = range(-coeff_range, coeff_range + 1)
    combos = list(product(rng, repeat=degree + 1))
    for acoef in combos:
        if all(c == 0 for c in acoef):
            continue
        a = _poly(acoef)
        for bcoef in combos:
            if bcoef[0] == 0 and all(c == 0 for c in bcoef[1:]):
                continue
            if scanned >= max_scan:
                return hits
            scanned += 1
            b = _poly(bcoef)
            cf = ContinuedFraction(a_fn=a, b_fn=b, text=f"a(n)={acoef}, b(n)={bcoef}")
            try:
                v = cf.value(dps=dps, terms=terms)
            except (ZeroDivisionError, ValueError, OverflowError):
                continue
            if v is None:
                continue
            # search mode: small coefficients + few PSLQ steps, so no-relation
            # cases (the vast majority) bail fast instead of grinding.
            rel, recip = anomaly.find_closed_form_pm(
                v, dps=dps, maxcoeff=1000, maxsteps=2000)
            if rel is None:
                continue
            key = rel.formula + str(recip)
            if key in seen:
                continue
            seen.add(key)
            hits.append(CFHit(text=cf.text, value=_fmt(v),
                              closed_form=rel.formula, reciprocal=recip))
            if len(hits) >= max_hits:
                return hits
    return hits


def _fmt(v) -> str:
    try:
        return f"{float(v):.12f}"
    except Exception:
        return str(v)
