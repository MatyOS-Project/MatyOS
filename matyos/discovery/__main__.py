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

from matyos.discovery.objects import Sequence, Series
from matyos.discovery.engine import DiscoveryEngine
from matyos.discovery import anomaly


def _recur(p: int, q: int, a0: int, a1: int, n: int = 10) -> list[int]:
    s = [a0, a1]
    while len(s) < n:
        s.append(p * s[-1] + q * s[-2])
    return s


def toy_seeds() -> list:
    # Two domains:
    #  - sequences: ratio -> a metallic constant (golden, silver)
    #  - series:    sum   -> a hidden constant (Basel -> pi^2/6, Leibniz -> pi/4)
    return [
        Sequence.of(_recur(1, 1, 17, 100), name="fib-type(17,100)"),
        Sequence.of(_recur(2, 1, 7, 50), name="silver-type(7,50)"),
        Series(term_fn=lambda n: 1 / (n * n), text="sum 1/n^2", start=1),
        Series(term_fn=lambda n: 1 / (n * n * n), text="sum 1/n^3", start=1),
        Series(term_fn=lambda n: 1 / n ** 4, text="sum 1/n^4", start=1),
        Series(term_fn=lambda n: (-1) ** n / (2 * n + 1), text="sum (-1)^n/(2n+1)", start=0),
        Series(term_fn=lambda n: 1 / (2 ** n + 1), text="sum 1/(2^n+1)", start=1),  # a mystery
        Sequence.of([0, 0, 1, 1, 2, 4, 7, 13, 24, 44, 81], name="tribonacci"),
    ]


def main(argv: list[str] | None = None) -> int:
    import sys
    argv = sys.argv[1:] if argv is None else argv
    engine = DiscoveryEngine(min_score=0.2)
    if "--loop" in argv:
        i = argv.index("--loop")
        rounds = int(argv[i + 1]) if i + 1 < len(argv) and argv[i + 1].isdigit() else 3
        summary = engine.loop(toy_seeds(), rounds=rounds)
        if "--json" in argv:
            import json
            print(json.dumps(summary, indent=2))
            return 0
        print(f"discovery loop: {summary['rounds_run']} rounds, "
              f"{summary['unique']} unique candidates in memory\n")
        for rec in summary["candidates"][:8]:
            lab = rec.get("label", {})
            tag = lab.get("status", "?")
            if lab.get("novelty"):
                tag += f" · {lab['novelty']}"
            cf = rec.get("closed_form", "").replace("closed form found (PSLQ): ", "")
            print(f"  [{rec['rank']}] score {rec['score']:.3f}  [{tag}]  {cf or '(no closed form)'}"
                  f"  (round {rec.get('round', '?')})")
        return 0
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
