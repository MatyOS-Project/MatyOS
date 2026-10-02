"""Domains for Stoqos — the pluggable substrate that lets one calibrated model
score REALISTIC bounds across different kinds of mathematics.

A :class:`Domain` is three things, and nothing more:

* ``functionals`` — a dict ``name -> f(point) -> float``. A *bound* is a pair
  ``a(point) <= b(point)`` for two functionals a, b.
* ``weak(rng)``   — a *small* list of evidence points (thin evidence: a bound
  holding here is only REALISTIC, it may still be false in the wider world).
* ``strong(seed)``— a *large* list of points (the truth proxy: a bound that holds
  here too is treated as true).

Every domain flows through the same evidence features
(:func:`matyos.discovery.stoqos.rich_features_from_values`), so a single model can
be trained jointly across all of them. Adding a domain is adding one entry here.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Domain:
    name: str
    functionals: dict           # name -> callable(point) -> float
    weak: "callable"            # (random.Random) -> list[point]
    strong: "callable"          # (int seed) -> list[point]


# --------------------------------------------------------------------------- #
# graphs — wraps the existing invariants + graph batteries
# --------------------------------------------------------------------------- #
def _graph_domain() -> Domain:
    from matyos.discovery import graph as G
    from matyos.discovery import stoqos as S
    return Domain(
        name="graphs",
        functionals=G.all_invariants(),
        weak=lambda rng: S.weak_battery(rng, size=10),
        strong=lambda seed: S.strong_battery(seed=seed, per_n=12),
    )


# --------------------------------------------------------------------------- #
# sequences — functionals over (sequence, n) points
# --------------------------------------------------------------------------- #
def _seqs(rng, n, lo=4, hi=11):
    out = []
    for _ in range(n):
        L = rng.randint(lo, hi); k = rng.random()
        if k < 0.4:
            s = sorted(rng.randint(1, 12) for _ in range(L))
        elif k < 0.7:
            s = [rng.randint(1, 12) for _ in range(L)]
        else:
            a = rng.randint(1, 4); s = [a * (i + 1) for i in range(L)]
        out.append(s)
    return out


def _seq_points(sequences):
    return [(s, n) for s in sequences for n in range(len(s))]


def _sequence_domain() -> Domain:
    F = {
        "val": lambda p: p[0][p[1]],
        "idx": lambda p: p[1] + 1,
        "idx2": lambda p: (p[1] + 1) ** 2,
        "prefmax": lambda p: max(p[0][:p[1] + 1]),
        "prefsum": lambda p: sum(p[0][:p[1] + 1]),
        "prefmean": lambda p: sum(p[0][:p[1] + 1]) / (p[1] + 1),
        "double": lambda p: 2 * p[0][p[1]],
    }
    return Domain(
        name="sequences",
        functionals=F,
        weak=lambda rng: _seq_points(_seqs(rng, 4, 4, 6)),
        strong=lambda seed: _seq_points(_seqs(random.Random(seed), 40, 6, 11)),
    )


# --------------------------------------------------------------------------- #
# number theory — arithmetic functions over integers
# --------------------------------------------------------------------------- #
def _factorize(n):
    f = {}
    d = 2
    while d * d <= n:
        while n % d == 0:
            f[d] = f.get(d, 0) + 1
            n //= d
        d += 1
    if n > 1:
        f[n] = f.get(n, 0) + 1
    return f


def _d(n):      # number of divisors
    p = 1
    for e in _factorize(n).values():
        p *= (e + 1)
    return p


def _sigma(n):  # sum of divisors
    p = 1
    for q, e in _factorize(n).items():
        p *= (q ** (e + 1) - 1) // (q - 1)
    return p


def _phi(n):    # Euler totient
    r = n
    for q in _factorize(n):
        r -= r // q
    return r


def _number_theory_domain() -> Domain:
    F = {
        "n": lambda n: float(n),
        "d": lambda n: float(_d(n)),
        "sigma": lambda n: float(_sigma(n)),
        "phi": lambda n: float(_phi(n)),
        "omega": lambda n: float(len(_factorize(n))),
        "bigomega": lambda n: float(sum(_factorize(n).values())),
        "isqrt": lambda n: float(math.isqrt(n)),
    }
    # extra non-monotone comparisons (2*omega, d vs isqrt, half-sigma) create
    # bounds that hold on thin evidence yet fail at highly-composite numbers.
    F["twiceomega"] = lambda n: 2.0 * len(_factorize(n))
    F["halfsigma"] = lambda n: _sigma(n) / 2.0
    return Domain(
        name="number_theory",
        functionals=F,
        weak=lambda rng: [rng.randint(2, 120) for _ in range(10)],
        strong=lambda seed: list(range(2, 600)),
    )


# --------------------------------------------------------------------------- #
# means — the AM–GM family over positive vectors
# --------------------------------------------------------------------------- #
def _mean_vecs(rng, n, lo=3, hi=7):
    return [[rng.randint(1, 20) for _ in range(rng.randint(lo, hi))] for _ in range(n)]


def _median(v):
    s = sorted(v); m = len(s) // 2
    return float(s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2)


def _number_means_domain() -> Domain:
    # The AM-GM chain gives always-true bounds; the extra functionals (twicemin,
    # halfmax, range, median, harmean) give bounds whose truth depends on the
    # vector — so the domain has real REALISTIC-but-false cases, not just positives.
    F = {
        "vmin": lambda v: float(min(v)),
        "harmean": lambda v: len(v) / sum(1.0 / x for x in v),
        "geomean": lambda v: math.exp(sum(math.log(x) for x in v) / len(v)),
        "mean": lambda v: sum(v) / len(v),
        "rms": lambda v: math.sqrt(sum(x * x for x in v) / len(v)),
        "vmax": lambda v: float(max(v)),
        "median": _median,
        "twicemin": lambda v: 2.0 * min(v),
        "halfmax": lambda v: max(v) / 2.0,
        "vrange": lambda v: float(max(v) - min(v)),
    }
    return Domain(
        name="means",
        functionals=F,
        weak=lambda rng: _mean_vecs(rng, 8),
        strong=lambda seed: _mean_vecs(random.Random(seed), 300),
    )


# --------------------------------------------------------------------------- #
# triangles — classic geometry inequalities over integer triangles
# --------------------------------------------------------------------------- #
def _triangle(rng):
    # a valid (non-degenerate) integer triangle: the third side lies strictly
    # inside (|a-b|, a+b), so area > 0 and the circumradius is finite.
    for _ in range(50):
        a = rng.randint(2, 20); b = rng.randint(2, 20)
        lo, hi = abs(a - b) + 1, a + b - 1
        if lo <= hi:
            return (a, b, rng.randint(lo, hi))
    return (3, 4, 5)


def _tris(rng, n):
    return [_triangle(rng) for _ in range(n)]


def _area(p):
    a, b, c = p; s = (a + b + c) / 2.0
    return math.sqrt(max(s * (s - a) * (s - b) * (s - c), 0.0))


def _triangle_domain() -> Domain:
    # Real geometry inequalities. Euler's inequality (tworadius <= circumradius,
    # i.e. 2r <= R) is an always-true bound; scale-dependent pairs (area vs
    # perimeter, inradius vs shortest side) hold on small triangles yet fail on
    # large ones -> genuine REALISTIC-but-false cases, so the domain has both
    # classes, not just positives.
    def r(p):   # inradius = area / semiperimeter
        a, b, c = p; return _area(p) / ((a + b + c) / 2.0)
    def R(p):   # circumradius = abc / (4 * area)
        a, b, c = p; A = _area(p); return (a * b * c) / (4.0 * A) if A > 0 else 0.0
    F = {
        "perimeter": lambda p: float(sum(p)),
        "semiperim": lambda p: sum(p) / 2.0,
        "area": _area,
        "inradius": r,
        "circumradius": R,
        "tworadius": lambda p: 2.0 * r(p),      # Euler: tworadius <= circumradius
        "longest": lambda p: float(max(p)),
        "shortest": lambda p: float(min(p)),
        "midside": lambda p: float(sorted(p)[1]),
        "height_long": lambda p: 2.0 * _area(p) / max(p),
    }
    return Domain(
        name="triangles",
        functionals=F,
        weak=lambda rng: _tris(rng, 8),
        strong=lambda seed: _tris(random.Random(seed), 300),
    )


# --------------------------------------------------------------------------- #
# primes — bounds over the nth prime (Bertrand's postulate, prime gaps, PNT)
# --------------------------------------------------------------------------- #
def _primes_upto(limit):
    sieve = [True] * (limit + 1)
    sieve[0] = sieve[1] = False
    for i in range(2, int(limit ** 0.5) + 1):
        if sieve[i]:
            for j in range(i * i, limit + 1, i):
                sieve[j] = False
    return [i for i in range(2, limit + 1) if sieve[i]]


_PRIMES = _primes_upto(4000)          # ~550 primes; point n is a 0-based index


def _primes_domain() -> Domain:
    # A point is an index n into the prime list; functionals are bounds over p_n.
    # Famous always-true bounds live here: Bertrand's postulate (p_{n+1} <= 2 p_n)
    # and n <= p_n. Scale-crossing pairs (n*ln n vs p_n, p_n vs n^2) hold for some
    # n yet fail for others, so the domain carries both classes.
    P = _PRIMES
    F = {
        "idx": lambda n: float(n + 1),                      # n (the ordinal)
        "prime": lambda n: float(P[n]),                     # p_n
        "next_prime": lambda n: float(P[n + 1]),            # p_{n+1}
        "twice_prime": lambda n: 2.0 * P[n],                # 2 p_n  (Bertrand)
        "gap": lambda n: float(P[n + 1] - P[n]),            # prime gap g_n
        "nlogn": lambda n: (n + 1) * math.log(n + 2),       # ~ p_n  (prime number thm)
        "half_prime": lambda n: P[n] / 2.0,
        "isqrt_prime": lambda n: float(math.isqrt(P[n])),
    }
    return Domain(
        name="primes",
        functionals=F,
        weak=lambda rng: [rng.randint(1, 60) for _ in range(10)],
        strong=lambda seed: list(range(1, 500)),
    )


def all_domains() -> list:
    """The domains Stoqos covers: graphs, sequences, number theory, means,
    triangles, primes."""
    return [_graph_domain(), _sequence_domain(), _number_theory_domain(),
            _number_means_domain(), _triangle_domain(), _primes_domain()]
