"""Numerical-anomaly detection by integer-relation finding (PSLQ).

Given a real number, search for a small integer relation against a basis of
mathematical constants. A hit means the number has a *closed form* — e.g. the
golden ratio (1+sqrt5)/2, or a rational multiple of pi. This is the core
Ramanujan-Machine move, and the one honest, fully-real signal in the engine.

Uses mpmath's PSLQ. mpmath is an optional dependency: if it is not installed,
``HAVE_PSLQ`` is False and callers fall back to a coarser known-constant check.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

try:
    import mpmath as mp
    HAVE_PSLQ = True
except Exception:  # pragma: no cover - exercised only when mpmath is absent
    HAVE_PSLQ = False


# Basis of constants PSLQ searches against, besides the unknown x itself.
# Names are used to render the discovered closed form.
def _basis():
    return [
        ("1", mp.mpf(1)),
        ("pi", mp.pi),
        ("pi^2", mp.pi ** 2),
        ("pi^3", mp.pi ** 3),
        ("pi^4", mp.pi ** 4),
        ("e", mp.e),
        ("sqrt2", mp.sqrt(2)),
        ("sqrt3", mp.sqrt(3)),
        ("sqrt5", mp.sqrt(5)),
        ("sqrt6", mp.sqrt(6)),
        ("sqrt7", mp.sqrt(7)),
        ("ln2", mp.log(2)),
        ("ln3", mp.log(3)),
        ("gamma", mp.euler),          # Euler-Mascheroni
        ("catalan", mp.catalan),      # Catalan's constant G
        ("zeta3", mp.zeta(3)),        # Apery's constant
    ]


# A genuine closed form is sparse: x equals a short combination of constants.
# Numerology, especially against a large basis, fits a *dense* relation with many
# terms. Capping the number of non-x terms is the strongest guard against it.
MAX_TERMS = 4


@dataclass(frozen=True)
class Relation:
    """A discovered integer relation a0*x + sum(ai*ci) = 0."""
    coeffs: tuple[int, ...]   # (a0, a1, ...), a0 multiplies x
    names: tuple[str, ...]    # ("x", "1", "pi", ...)
    formula: str              # human-readable  "x = (1 + sqrt5)/2"


def find_closed_form(value, dps: int = 50, maxcoeff: int = 10 ** 5) -> "Relation | None":
    """Return a closed form for ``value``, or None.

    ``value`` may be a Fraction (used exactly), an int, or a string/float. PSLQ
    needs the input to many more digits than the coefficient size, so callers
    should pass an exact Fraction where possible (e.g. a ratio of exact terms).
    A relation is accepted only if it actually involves x (a0 != 0) and it
    reproduces ``value`` back to within the working tolerance.
    """
    if not HAVE_PSLQ:
        return None
    mp.mp.dps = dps
    x = _to_mpf(value)
    basis = _basis()
    vec = [x] + [c for _, c in basis]
    names = ("x",) + tuple(n for n, _ in basis)
    rel = mp.pslq(vec, maxcoeff=maxcoeff, maxsteps=10 ** 5)
    if not rel or rel[0] == 0:
        return None
    # Reject a pure-rational "closed form": if the only non-x term is the "1"
    # basis element, PSLQ has merely rationalised x (e.g. a ratio settling near 1).
    # That is not a constant discovery, so it does not count as an anomaly.
    nonzero_basis = [n for c, n in zip(rel[1:], names[1:]) if c != 0]
    if nonzero_basis == ["1"] or not nonzero_basis:
        return None
    # Sparsity gate: reject dense relations — numerology, not a closed form.
    if len(nonzero_basis) > MAX_TERMS:
        return None
    # Confirm the relation really holds (guard against a spurious PSLQ hit).
    residual = sum(mp.mpf(c) * v for c, v in zip(rel, vec))
    if abs(residual) > mp.mpf(10) ** (-(dps - 8)):
        return None
    # Significance gate: a relation is only meaningful when the working precision
    # comfortably exceeds the size of its coefficients — otherwise PSLQ has just
    # fitted noise with big integers (numerology). Require the total digit-length
    # of the non-zero coefficients, plus a margin, to fit inside dps.
    sig_digits = sum(len(str(abs(int(c)))) for c in rel if c != 0)
    if dps < sig_digits + 12:
        return None
    return Relation(coeffs=tuple(int(c) for c in rel), names=names,
                    formula=_render(rel, names))


def value_of(rel: "Relation", dps: int = 50):
    """Reconstruct the numeric value a relation asserts for x, at precision dps.

    From a0*x + sum(ai*ci) = 0 we have x = -(sum ai*ci)/a0. Returns an mpf, or
    None if mpmath is unavailable. Used to test a discovered closed form against
    fresh data (refutation), independently of how it was found.
    """
    if not HAVE_PSLQ:
        return None
    mp.mp.dps = dps
    consts = {"1": mp.mpf(1)}
    consts.update({n: c for n, c in _basis()})
    a0 = rel.coeffs[0]
    acc = mp.mpf(0)
    for c, n in zip(rel.coeffs[1:], rel.names[1:]):
        if c:
            acc += mp.mpf(c) * consts[n]
    return -acc / mp.mpf(a0)


def _to_mpf(value):
    if isinstance(value, Fraction):
        return mp.mpf(value.numerator) / mp.mpf(value.denominator)
    if isinstance(value, mp.mpf):
        return value                      # already high-precision (e.g. a series value)
    return mp.mpf(str(value))


def _render(coeffs, names) -> str:
    """Render  a0*x + sum(ai*ci) = 0  as  x = (sum bi*ci) / d  in readable form.

    From a0*x = -sum(ai*ci): the numerator coefficient of ci is bi = -ai, over
    denominator a0. Normalise so the denominator is positive.
    """
    a0 = int(coeffs[0])
    s = 1 if a0 > 0 else -1
    denom = a0 * s                       # = |a0|
    parts = []
    for a, n in zip(coeffs[1:], names[1:]):
        b = -int(a) * s                  # numerator coefficient of this constant
        if b == 0:
            continue
        mag = abs(b)
        token = "1" if n == "1" else n
        piece = str(mag) if token == "1" else (token if mag == 1 else f"{mag}*{token}")
        parts.append((b, piece))
    if not parts:
        return "x = 0"
    body = ""
    for i, (b, piece) in enumerate(parts):
        if i == 0:
            body = ("-" if b < 0 else "") + piece
        else:
            body += (" - " if b < 0 else " + ") + piece
    if denom == 1:
        return f"x = {body}"
    return f"x = ({body}) / {denom}"
