"""A sound certificate engine for the **means** domain — Doxa's first *prover*.

The means functionals are exactly power means of a positive vector:

    vmin = M_{-inf},  harmean = M_{-1},  geomean = M_0,
    mean = M_1,       rms     = M_2,     vmax    = M_{+inf}.

The **power-mean inequality** (``M_s <= M_t`` whenever ``s <= t``, for positive
reals) proves the entire ordered chain; the adjacent steps carry an explicit
**sum-of-squares** witness (e.g. AM-GM for two terms is ``(sqrt a - sqrt b)^2 >= 0``).
Together with order-statistic facts (``min <= median <= max``) and positivity
(``max/2 <= max``, ``min <= 2*min``), this *certifies* — i.e. **proves** — a bound,
not merely scores it.

Soundness is the whole point: :func:`certify` returns a proof **only** for a
genuine theorem, never for a false or merely-plausible bound. Everything it cannot
prove it declines (returns ``None``), leaving the claim at the REALISTIC level for
the scorer. This is exactly the kernel's discipline: assert TRUE only with a proof.

The engine is means-specific by design — it exploits that domain's power-mean
structure. It has zero dependencies.
"""
from __future__ import annotations

INF = float("inf")

# power-mean exponent of each functional (None => not a power mean)
_EXP = {"vmin": -INF, "harmean": -1.0, "geomean": 0.0,
        "mean": 1.0, "rms": 2.0, "vmax": INF}

# explicit sum-of-squares witness for the adjacent (two-term) power-mean step
_SOS2 = {
    (-1.0, 0.0): "GM–HM: (√a−√b)² ≥ 0",
    (0.0, 1.0):  "AM–GM: (√a−√b)² ≥ 0",
    (1.0, 2.0):  "QM–AM: (a−b)²/4 ≥ 0",
}

# functionals bounded below by the minimum (min is the least entry = M_{-inf})
_MIN_LOWER = {"median", "harmean", "geomean", "mean", "rms", "vmax", "twicemin"}
# functionals bounded above by the maximum (max is the greatest entry = M_{+inf})
_MAX_UPPER = {"median", "vrange", "halfmax", "harmean", "geomean", "mean", "rms"}


def _fmt(e: float) -> str:
    return "−∞" if e == -INF else ("+∞" if e == INF else ("%g" % e))


def certify(a: str, b: str) -> "str | None":
    """Return a human-readable proof that ``a(v) <= b(v)`` for every positive
    vector ``v``, or ``None`` if the engine cannot prove it.

    **Sound:** only ever cites a real theorem (power-mean inequality, an explicit
    sum-of-squares, an order statistic, or positivity). It never certifies a false
    or unproven bound — those return ``None`` and stay REALISTIC.
    """
    ea, eb = _EXP.get(a), _EXP.get(b)
    # 1. the power-mean chain
    if ea is not None and eb is not None and ea <= eb:
        proof = f"power-mean inequality: M_{{{_fmt(ea)}}} ≤ M_{{{_fmt(eb)}}}"
        step = _SOS2.get((ea, eb))
        return proof + (f"  ·  SOS: {step}" if step else "")
    # 2. min is the least entry, max is the greatest
    if a == "vmin" and b in _MIN_LOWER:
        return f"min ≤ {b}  (min is the least entry, M_{{−∞}})"
    if b == "vmax" and a in _MAX_UPPER:
        return f"{a} ≤ max  (max is the greatest entry, M_{{+∞}})"
    # 3. order statistics and positivity (entries > 0)
    if a == "vmin" and b == "median":
        return "min ≤ median  (order statistic)"
    if a == "median" and b == "vmax":
        return "median ≤ max  (order statistic)"
    if a == "vmin" and b == "twicemin":
        return "min ≤ 2·min  (entries positive)"
    if a == "halfmax" and b == "vmax":
        return "max/2 ≤ max  (max > 0)"
    return None


def is_means_pair(a: str, b: str) -> bool:
    """Whether both names are means-domain functionals the engine knows."""
    known = set(_EXP) | {"median", "twicemin", "halfmax", "vrange"}
    return a in known and b in known
