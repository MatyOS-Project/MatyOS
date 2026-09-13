"""Phase-1 discovery demo. Run it through the CLI:  matyos discover

Seeds a few integer sequences and runs one generation of the engine. The signals
are real, not scripted:

- Fibonacci  -> transfers to its recurrence, and PSLQ discovers the ratio's
  closed form  x = (1 + sqrt5)/2  (the golden ratio).
- Pell       -> ratio closed form  x = 1 + sqrt2  (the silver ratio).
- OEIS is queried live to say whether each sequence is already known.

Needs mpmath for PSLQ (`pip install mpmath`); without it the scorer falls back to
a coarse known-constant check and says so. OEIS runs live, falling back to a small
offline table with no network.
"""

from __future__ import annotations

from matyos.discovery.objects import Sequence
from matyos.discovery.engine import DiscoveryEngine
from matyos.discovery import anomaly


def _recur(p: int, q: int, a0: int, a1: int, n: int = 10) -> list[int]:
    s = [a0, a1]
    while len(s) < n:
        s.append(p * s[-1] + q * s[-2])
    return s


def toy_seeds() -> list[Sequence]:
    # Same recurrences as Fibonacci (ratio -> golden) and Pell (ratio -> silver),
    # but with unusual starting values that are NOT catalogued in OEIS. So the
    # engine finds a real closed form AND reports no prior art — the shape of a
    # candidate worth a human's look.
    return [
        Sequence.of(_recur(1, 1, 17, 100), name="fib-type(17,100)"),
        Sequence.of(_recur(2, 1, 7, 50), name="silver-type(7,50)"),
        Sequence.of([0, 1, 1, 2, 3, 5, 8, 13, 21, 34], name="fibonacci (known, for contrast)"),
    ]


def main(argv: list[str] | None = None) -> int:
    import sys
    argv = sys.argv[1:] if argv is None else argv
    engine = DiscoveryEngine(min_score=0.2)
    if "--json" in argv:
        import json
        print(json.dumps({"candidates": engine.records(toy_seeds())}, indent=2))
        return 0
    if not anomaly.HAVE_PSLQ:
        print("(note: mpmath not installed — PSLQ off, using coarse fallback. "
              "`pip install mpmath` for real closed-form discovery.)\n")
    print(engine.report(toy_seeds()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
