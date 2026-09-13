"""Generator / Mutator.

Produces new candidate objects from existing ones. The standard evolutionary moves
(compose, generalize, specialize) are here in toy form. The move that matters — the
one no existing discovery system runs as its core loop — is
:func:`cross_domain_transfer`: take a structure from domain A, re-express it in
domain B's language, and see whether the translation yields something nontrivial.

This scaffold implements exactly one transfer direction end-to-end:
``sequence -> formula`` via linear-recurrence detection. That is enough to make the
core mechanic real on the toy loop (a Fibonacci prefix transfers to its closed form
signal), while the general N-domains-by-M-domains transfer table is left as future
work.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Iterator

from matyos.discovery.objects import MathObject, Sequence, Formula


def mutate(obj: MathObject) -> Iterator[MathObject]:
    """Yield local mutations of ``obj`` — the within-domain evolutionary moves.

    Toy repertoire for sequences: first differences (specialize toward structure)
    and partial sums (generalize). Other domains yield nothing yet.
    """
    if isinstance(obj, Sequence) and len(obj.terms) >= 2:
        diffs = tuple(b - a for a, b in zip(obj.terms, obj.terms[1:]))
        yield Sequence(provenance=f"diff({obj.name or obj.key()})", terms=diffs,
                       name=f"Δ{obj.name}".strip("Δ"))
        sums: list[Fraction] = []
        acc = Fraction(0)
        for t in obj.terms:
            acc += t
            sums.append(acc)
        yield Sequence(provenance=f"partial_sum({obj.name or obj.key()})",
                       terms=tuple(sums), name=f"Σ{obj.name}".strip("Σ"))


def cross_domain_transfer(obj: MathObject) -> Iterator[MathObject]:
    """Re-express ``obj`` in another domain's language.

    Implemented direction: ``sequence -> formula``. We try to fit the sequence to
    an order-2 linear recurrence ``a[n] = p*a[n-1] + q*a[n-2]`` with rational
    ``p, q``. If a consistent fit exists, we emit a :class:`Formula` whose value is
    the same recurrence evaluated freshly — a closed *rule* recovered from raw
    terms. The transfer is deliberately shallow; its point is to demonstrate the
    mechanic, and the scorer decides whether the result is interesting.
    """
    if isinstance(obj, Sequence):
        rec = _fit_order2_recurrence(obj.terms)
        if rec is not None:
            p, q = rec
            a0, a1 = obj.terms[0], obj.terms[1]

            def make(p: Fraction, q: Fraction, a0: Fraction, a1: Fraction):
                def fn(n: int) -> Fraction:
                    x, y = a0, a1
                    if n == 0:
                        return x
                    if n == 1:
                        return y
                    for _ in range(2, n + 1):
                        x, y = y, p * y + q * x
                    return y
                return fn

            text = f"a[n] = ({p})*a[n-1] + ({q})*a[n-2],  a0={a0}, a1={a1}"
            yield Formula(provenance=f"transfer:sequence->formula({obj.name or obj.key()})",
                          fn=make(p, q, a0, a1), text=text)


def _fit_order2_recurrence(terms: tuple[Fraction, ...]) -> tuple[Fraction, Fraction] | None:
    """Solve for rational ``p, q`` in ``a[n] = p*a[n-1] + q*a[n-2]``.

    Uses the first two equations (indices 2 and 3) and then checks the fit against
    every remaining term. Returns ``None`` if there are too few terms, the system
    is singular, or the recurrence does not reproduce the whole prefix.
    """
    if len(terms) < 4:
        return None
    a0, a1, a2, a3 = terms[0], terms[1], terms[2], terms[3]
    # [a1 a0][p]   [a2]
    # [a2 a1][q] = [a3]
    det = a1 * a1 - a2 * a0
    if det == 0:
        return None
    p = (a2 * a1 - a3 * a0) / det
    q = (a1 * a3 - a2 * a2) / det
    for n in range(2, len(terms)):
        if p * terms[n - 1] + q * terms[n - 2] != terms[n]:
            return None
    return p, q
