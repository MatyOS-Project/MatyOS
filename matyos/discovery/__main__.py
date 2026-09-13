"""Toy discovery loop. Run it through the CLI:  matyos discover

Seeds a few integer sequences and runs one generation of the discovery engine.
The honest signal to watch: the Fibonacci prefix cross-domain-transfers into its
closed recurrence rule, whose consecutive-term ratio is detected as a numerical
anomaly matching the golden ratio phi. That match is real, not scripted — the
scorer rediscovers it from the terms.
"""

from __future__ import annotations

from matyos.discovery.objects import Sequence
from matyos.discovery.engine import DiscoveryEngine


def toy_seeds() -> list[Sequence]:
    return [
        Sequence.of([0, 1, 1, 2, 3, 5, 8, 13, 21, 34], name="fib"),
        Sequence.of([2, 4, 6, 8, 10, 12], name="evens"),          # boring arithmetic
        Sequence.of([1, 2, 4, 8, 16, 32], name="pow2"),
    ]


def main() -> int:
    engine = DiscoveryEngine(min_score=0.2)
    print(engine.report(toy_seeds()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
