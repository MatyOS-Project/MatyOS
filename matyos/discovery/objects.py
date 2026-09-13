"""Object Representation Layer.

A generic vocabulary for the *objects* mathematics is about — sequences, formulas,
graphs, operators — rather than proof terms. This is the language-design problem
MatyOS v2 is actually suited to own: it is not inheriting Lean's proof-term model,
so it is free to represent a candidate discovery in whatever form makes its
structure computable.

Only two concrete kinds are implemented in this scaffold: :class:`Sequence` and
:class:`Formula`. They are enough to run the toy loop and to exercise a real
cross-domain transfer (a sequence re-expressed as a closed-form formula). Graphs,
operators and structures are named in the design doc and left as future kinds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Callable, Sequence as _Seq


@dataclass(frozen=True)
class MathObject:
    """Base class for a representable mathematical object.

    ``domain`` names the domain the object currently lives in (e.g. ``"sequence"``,
    ``"formula"``). ``provenance`` records how the object was produced — a short
    human-readable trail such as ``"seed"`` or ``"transfer:sequence->formula"`` —
    so the triage report can explain where a candidate came from.
    """

    domain: str
    provenance: str = "seed"

    def key(self) -> str:
        """A stable identity string, used to deduplicate candidates."""
        raise NotImplementedError


@dataclass(frozen=True)
class Sequence(MathObject):
    """A finite prefix of an integer or rational sequence.

    We store a prefix (the terms we have computed) rather than a generating rule,
    because the scorer works numerically on the terms. ``name`` is optional and
    only used for reporting.
    """

    terms: tuple[Fraction, ...] = ()
    name: str = ""
    domain: str = field(default="sequence", init=False)

    @staticmethod
    def of(values: _Seq[int | float | Fraction], name: str = "", provenance: str = "seed") -> "Sequence":
        terms = tuple(Fraction(v) for v in values)
        return Sequence(provenance=provenance, terms=terms, name=name)

    def key(self) -> str:
        return "seq:" + ",".join(str(t) for t in self.terms)


@dataclass(frozen=True)
class Formula(MathObject):
    """A closed-form expression over a single index variable ``n`` (0-based).

    The expression is carried as a Python callable plus a human-readable ``text``
    label. ``fn(n)`` must return a :class:`~fractions.Fraction` (or something that
    coerces to one). Keeping the callable lets the scorer evaluate the formula
    numerically without a bespoke expression evaluator; ``text`` is what gets
    shown to a human.
    """

    fn: Callable[[int], object] = None  # type: ignore[assignment]
    text: str = ""
    domain: str = field(default="formula", init=False)

    def evaluate_prefix(self, length: int) -> tuple[Fraction, ...]:
        return tuple(Fraction(self.fn(n)) for n in range(length))

    def key(self) -> str:
        return "formula:" + self.text
