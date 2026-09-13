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


def toy_seeds() -> list[Sequence]:
    return [
        Sequence.of([0, 1, 1, 2, 3, 5, 8, 13, 21, 34], name="fibonacci"),
        Sequence.of([0, 1, 2, 5, 12, 29, 70, 169, 408], name="pell"),
        Sequence.of([2, 4, 6, 8, 10, 12], name="evens"),  # arithmetic: honest miss
    ]


def main() -> int:
    if not anomaly.HAVE_PSLQ:
        print("(note: mpmath not installed — PSLQ off, using coarse fallback. "
              "`pip install mpmath` for real closed-form discovery.)\n")
    engine = DiscoveryEngine(min_score=0.2)
    print(engine.report(toy_seeds()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
