"""Continued-fraction search — the Ramanujan-Machine move.

Enumerate simple polynomial continued fractions b0 + a1/(b1 + a2/(b2 + ...)),
compute each value to high precision, and hunt a closed form for the value (or
its reciprocal). A hit is a continued-fraction identity for a constant — the kind
of thing the Ramanujan Machine discovered.

The search is deliberately bounded (small integer polynomial coefficients, low
degree). It is a *candidate generator*: every hit still needs a human/proof, and
most bounded searches only rediscover known identities — but this is the one part
of MatyOS whose output could, in principle, be new.

Two outputs:

- ``search`` returns **hits**: CFs whose value (or reciprocal) is a closed form in
  the constant basis. Almost always these are known identities — proof the machine
  works, not a discovery.
- ``frontier`` returns **mysteries**: CFs that converge to a *stable* value that is
  not a small rational, not a small-degree algebraic number, and has no closed form
  in the basis. **Empirically this is NOT a useful discovery signal.** A measured
  scan (600 CFs, full basis, degree 2, coeffs -2..2) produced 0 known-constant hits
  and flagged 507 of 600 as "mysteries" — because *almost every* polynomial CF
  converges to a nondescript transcendental with no nice name. "Unnameable" is the
  generic case, not a rare lead. Keep ``frontier`` as a diagnostic, but do not read
  its output as candidate discoveries. The real Ramanujan-Machine signal is a
  ``search`` **hit** to a *known* constant via a non-obvious CF; that is where a new
  identity can live, and it needs a coefficient family that actually lands on such
  constants (this negative result says the -2..2 family, as scanned, does not).
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


@dataclass(frozen=True)
class CFMystery:
    text: str            # the continued fraction, described
    value: str           # decimal value (stable to the working precision)
    note: str = "stable value, no closed form in basis, not a small rational"


def _poly(coeffs):
    """Return a function n -> c0 + c1*n + c2*n^2 for the given integer coeffs."""
    return lambda n: sum(c * n ** i for i, c in enumerate(coeffs))


def _combos(coeff_range: int, degree: int):
    rng = range(-coeff_range, coeff_range + 1)
    return list(product(rng, repeat=degree + 1))


def _scan(coeff_range: int, degree: int, dps: int, max_scan: int, terms: int):
    """Yield (cf, value) for each non-degenerate polynomial CF, up to max_scan.

    Shared by ``search`` and ``frontier`` so a CF is enumerated the same way for
    both. Skips zero a(n) and zero b(n), and CFs that fail to evaluate.
    """
    scanned = 0
    combos = _combos(coeff_range, degree)
    for acoef in combos:
        if all(c == 0 for c in acoef):
            continue
        a = _poly(acoef)
        for bcoef in combos:
            if bcoef[0] == 0 and all(c == 0 for c in bcoef[1:]):
                continue
            if scanned >= max_scan:
                return
            scanned += 1
            b = _poly(bcoef)
            cf = ContinuedFraction(a_fn=a, b_fn=b, text=f"a(n)={acoef}, b(n)={bcoef}")
            try:
                v = cf.value(dps=dps, terms=terms)
            except (ZeroDivisionError, ValueError, OverflowError):
                continue
            if v is None:
                continue
            yield cf, v


def search(coeff_range: int = 2, degree: int = 2, dps: int = 80,
           max_hits: int = 25, max_scan: int = 4000, terms: int = 150,
           core: bool = True) -> list[CFHit]:
    """Scan polynomial continued fractions and return the identities found.

    coeff_range: integer coefficients range over -coeff_range..coeff_range.
    degree:      polynomial degree for a(n) and b(n).
    max_scan:    hard cap on continued fractions examined.
    core:        screen against the small fast constant basis (default). ~30x
                 faster (~0.2s/CF vs ~6s); catches the common pi/e/sqrt identities.
                 Pass core=False for the full basis (zeta, Catalan, ...) — a much
                 slower, overnight-scale search.
    Returns at most ``max_hits`` CFHits. Requires mpmath.
    """
    if not anomaly.HAVE_PSLQ:
        return []
    hits: list[CFHit] = []
    seen: set[str] = set()
    for cf, v in _scan(coeff_range, degree, dps, max_scan, terms):
        # search mode: small coefficients + few PSLQ steps, so no-relation
        # cases (the vast majority) bail fast instead of grinding.
        rel, recip = anomaly.find_closed_form_pm(
            v, dps=dps, maxcoeff=1000, maxsteps=2000, core=core)
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


def frontier(coeff_range: int = 2, degree: int = 2, dps: int = 80,
             max_hits: int = 25, max_scan: int = 4000, terms: int = 150,
             core: bool = False) -> list[CFMystery]:
    """Scan CFs and return the *mysteries*: stable, no closed form, not rational.

    A mystery is a CF whose value is stable (agrees at ``dps`` and ``dps+25``
    digits, so it is not numerical noise), is not a small rational, is **not a
    root of a small integer polynomial** (algebraic numbers are known, not leads),
    and has no closed form for the value or its reciprocal. NOTE: a measured scan
    found this flags ~85% of CFs (generic transcendentals), so it is a diagnostic,
    NOT a discovery signal — see the module docstring. Labelled unknown, never a
    claim.

    ``core=False`` by default: mysteries are only meaningful against the *full*
    basis, else a value the small basis can't name (e.g. involving ln3, Catalan)
    is falsely flagged. This makes ``frontier`` the slow, overnight-scale search.
    Requires mpmath.
    """
    if not anomaly.HAVE_PSLQ:
        return []
    out: list[CFMystery] = []
    seen: set[str] = set()
    for cf, v in _scan(coeff_range, degree, dps, max_scan, terms):
        rel, _recip = anomaly.find_closed_form_pm(
            v, dps=dps, maxcoeff=1000, maxsteps=2000, core=core)
        if rel is not None:
            continue                              # a closed form exists → not a mystery
        if _is_small_rational(v, dps):
            continue                              # a plain fraction → not interesting
        if _is_algebraic(v, dps):
            continue                              # root of a small polynomial → known, not a lead
        if not _is_stable(cf, v, dps, terms):
            continue                              # numerical noise, not a constant
        key = _fmt(v)
        if key in seen:
            continue
        seen.add(key)
        out.append(CFMystery(text=cf.text, value=key))
        if len(out) >= max_hits:
            return out
    return out


def _is_stable(cf, v, dps: int, terms: int) -> bool:
    """True if the CF value is unchanged (to ~dps digits) at higher precision.

    Recompute at dps+25 with more terms; a real convergent constant agrees, a
    slowly-drifting or non-converging CF does not.
    """
    try:
        v2 = cf.value(dps=dps + 25, terms=terms + 100)
    except (ZeroDivisionError, ValueError, OverflowError):
        return False
    if v2 is None:
        return False
    import mpmath as mp
    with mp.workdps(dps + 25):
        try:
            return mp.almosteq(mp.mpf(str(v)), v2, rel_eps=mp.mpf(10) ** (-(dps - 5)))
        except Exception:
            return False


def _is_small_rational(v, dps: int, max_den: int = 10 ** 6) -> bool:
    """True if v is (numerically) a rational p/q with |q| <= max_den.

    PSLQ on [v, 1]: a relation c0*v + c1 = 0 means v = -c1/c0, a rational. The
    closed-form search already excludes these (basis contains 1), but frontier
    screens independently so it never depends on that ordering.
    """
    import mpmath as mp
    with mp.workdps(dps):
        try:
            rel = mp.pslq([mp.mpf(str(v)), mp.mpf(1)], maxcoeff=max_den, maxsteps=2000)
        except (ValueError, RuntimeError):
            return False
    return rel is not None and rel[0] != 0


def _is_algebraic(v, dps: int, max_deg: int = 6, maxcoeff: int = 10 ** 5) -> bool:
    """True if v is a root of a small integer polynomial (degree <= max_deg).

    PSLQ on [1, v, v^2, ..., v^deg] finds an integer relation = a minimal
    polynomial. A frontier mystery must clear this: most stable CF values the
    constant basis can't name are just ordinary algebraic numbers (roots of
    quadratics/cubics), which are known — not leads. Only a value with *no* such
    small minimal polynomial is worth a human's time.
    """
    import mpmath as mp
    with mp.workdps(dps):
        x = mp.mpf(str(v))
        for deg in range(2, max_deg + 1):
            try:
                rel = mp.pslq([x ** i for i in range(deg + 1)],
                              maxcoeff=maxcoeff, maxsteps=10 ** 4)
            except (ValueError, RuntimeError):
                rel = None
            if rel is not None and any(c != 0 for c in rel[1:]):
                return True
    return False


def _fmt(v) -> str:
    try:
        return f"{float(v):.12f}"
    except Exception:
        return str(v)
