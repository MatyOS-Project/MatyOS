"""Famous open problems — an honest engagement layer.

MatyOS cannot prove the Riemann Hypothesis, Goldbach, the Twin Prime conjecture,
or Collatz, and this module never claims to. For each it offers exactly four honest
capabilities: **state** it formally in Lean (`state`), **verify a finite range**
(`verify_finite`, always labelled "NOT a proof"), **explore the adjacent sequence**
with the discovery engine (`explore_adjacent`), and **track** the known results
(`status`). Every problem hard-codes ``provable_by_matyos = False`` for the
conjecture itself, and no function here returns "proved" for a conjecture-level
statement. See docs/hard-problems.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---- small, honest number theory (for finite verification / adjacent data) ----

def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True


def _primes_upto(n: int) -> list[int]:
    if n < 2:
        return []
    sieve = bytearray([1]) * (n + 1)
    sieve[0] = sieve[1] = 0
    for i in range(2, int(n ** 0.5) + 1):
        if sieve[i]:
            sieve[i * i::i] = bytearray(len(sieve[i * i::i]))
    return [i for i in range(2, n + 1) if sieve[i]]


def _collatz_step(n: int) -> int:
    return n // 2 if n % 2 == 0 else 3 * n + 1


# ---- honest result type: finite evidence is never a proof -----------------------

@dataclass(frozen=True)
class FiniteEvidence:
    """The outcome of checking a conjecture on a bounded range. Not a proof."""
    problem: str
    checked_up_to: int
    holds: bool
    counterexample: int | None = None

    def __repr__(self) -> str:
        cx = f", counterexample={self.counterexample}" if self.counterexample is not None else ""
        return (f"<FiniteEvidence {self.problem}: checked up to {self.checked_up_to}, "
                f"holds={self.holds}{cx} — finite check, NOT a proof>")


@dataclass(frozen=True)
class FamousProblem:
    key: str
    name: str
    lean_statement: str
    lean_in_mathlib: bool            # does the statement typecheck against mathlib as written?
    known_results: str
    matyos_can: tuple
    matyos_cannot: str
    provable_by_matyos: bool = field(default=False, init=False)   # hard-coded: never provable here

    def conjecture(self):
        """A `Conjecture` for the problem — stated, never proved."""
        from matyos.discovery.formal import Conjecture
        return Conjecture(
            claim=self.name,
            lean_statement=self.lean_statement,
            label={"status": "open (famous problem)", "novelty": "known-open",
                   "provable_by_matyos": False, "lean_in_mathlib": self.lean_in_mathlib},
            source="famous-problem",
        )


# ---- the registry: formal statements + honest capability map --------------------

_HDR = "import Mathlib\n\n"

REGISTRY: dict[str, FamousProblem] = {
    "goldbach": FamousProblem(
        key="goldbach", name="Goldbach's conjecture (strong)",
        lean_statement=_HDR + ("theorem matyos_goldbach :\n"
                               "    ∀ n : ℕ, Even n → 2 < n → "
                               "∃ p q, p.Prime ∧ q.Prime ∧ n = p + q := by\n  sorry\n"),
        lean_in_mathlib=True,
        known_results="Verified to 4×10^18; Chen's theorem (n = p + P₂); ternary Goldbach proved (Helfgott 2013).",
        matyos_can=("state in Lean", "verify every even n up to N", "explore the Goldbach-partition-count sequence"),
        matyos_cannot="prove the ∀ statement",
    ),
    "twin_primes": FamousProblem(
        key="twin_primes", name="Twin Prime conjecture",
        lean_statement=_HDR + ("theorem matyos_twin_primes :\n"
                               "    ∀ N : ℕ, ∃ p, N < p ∧ p.Prime ∧ (p + 2).Prime := by\n  sorry\n"),
        lean_in_mathlib=True,
        known_results="Infinitude open; Zhang 2013 (bounded gaps); Maynard/Polymath gap ≤ 246.",
        matyos_can=("state in Lean", "enumerate twin pairs below N", "explore the twin-pair count sequence"),
        matyos_cannot="prove infinitude",
    ),
    "collatz": FamousProblem(
        key="collatz", name="Collatz (3n+1) conjecture",
        lean_statement=_HDR + ("def collatz (n : ℕ) : ℕ := if n % 2 = 0 then n / 2 else 3 * n + 1\n\n"
                               "theorem matyos_collatz :\n"
                               "    ∀ n : ℕ, 0 < n → ∃ k, collatz^[k] n = 1 := by\n  sorry\n"),
        lean_in_mathlib=True,          # collatz is defined inline here, then the statement is over it
        known_results="Verified to ~2^69; Tao 2019 (almost all orbits reach small values); open in general.",
        matyos_can=("define collatz + state in Lean", "verify every n up to N reaches 1", "explore the stopping-time sequence"),
        matyos_cannot="prove it for all n",
    ),
    "riemann": FamousProblem(
        key="riemann", name="Riemann Hypothesis",
        lean_statement=_HDR + ("-- mathlib states RiemannHypothesis; MatyOS can only re-state it.\n"
                               "theorem matyos_riemann : RiemannHypothesis := by\n  sorry\n"),
        lean_in_mathlib=True,          # mathlib defines `RiemannHypothesis : Prop`
        known_results="~10^13 zeros verified on the critical line; open since 1859.",
        matyos_can=("state in Lean (mathlib's RiemannHypothesis)", "track the known state"),
        matyos_cannot="represent ζ or engage the analytic object at all — the least reachable of the four",
    ),
}


# ---- the four honest capabilities ----------------------------------------------

def state(key: str):
    """Return the `Conjecture` for a famous problem — stated, never proved."""
    return REGISTRY[key].conjecture()


def status(key: str) -> dict:
    """The honest state of a problem: what is known, and what MatyOS can/cannot do."""
    p = REGISTRY[key]
    return {"name": p.name, "known_results": p.known_results,
            "matyos_can": list(p.matyos_can), "matyos_cannot": p.matyos_cannot,
            "provable_by_matyos": p.provable_by_matyos,
            "lean_statement": p.lean_statement}


def verify_finite(key: str, upto: int) -> FiniteEvidence:
    """Check a conjecture on a bounded range. Returns `FiniteEvidence` — never a proof.

    Supported for goldbach / twin_primes / collatz (finitely checkable); riemann has
    no finite check MatyOS can perform, and raises to say so honestly."""
    if key == "goldbach":
        primes = set(_primes_upto(upto))
        plist = sorted(primes)
        for n in range(4, upto + 1, 2):
            if not any((n - p) in primes for p in plist if p <= n // 2):
                return FiniteEvidence("goldbach", upto, False, counterexample=n)
        return FiniteEvidence("goldbach", upto, True)
    if key == "twin_primes":
        # the claim is *infinitude*, which no finite range can confirm or refute;
        # report honestly that finite data cannot settle it (use explore_adjacent
        # for the actual twin-pair counts).
        raise ValueError("twin_primes asserts infinitude — no finite check settles it; "
                         "use explore_adjacent for twin-pair data")
    if key == "collatz":
        for n in range(1, upto + 1):
            m, steps = n, 0
            while m != 1 and steps < 10_000:
                m = _collatz_step(m); steps += 1
            if m != 1:
                return FiniteEvidence("collatz", upto, False, counterexample=n)
        return FiniteEvidence("collatz", upto, True)
    if key == "riemann":
        raise ValueError("riemann has no finite check MatyOS can perform (no zeta representation)")
    raise KeyError(key)


def _adjacent_sequence(key: str, upto: int) -> list[int]:
    """The integer sequence a problem generates, for the discovery engine to explore."""
    if key == "collatz":                       # stopping times
        out = []
        for n in range(1, upto + 1):
            m, steps = n, 0
            while m != 1 and steps < 10_000:
                m = _collatz_step(m); steps += 1
            out.append(steps)
        return out
    if key == "goldbach":                      # number of Goldbach partitions of 2n
        primes = set(_primes_upto(2 * upto))
        return [sum(1 for p in _primes_upto(n) if p <= n // 2 and (n - p) in primes)
                for n in range(4, 2 * upto + 1, 2)]
    if key == "twin_primes":                   # the twin-pair lower members
        return [p for p in _primes_upto(upto) if _is_prime(p + 2)]
    raise ValueError(f"no adjacent sequence for {key}")


def explore_adjacent(key: str, upto: int = 60) -> dict:
    """Run the discovery engine on the problem's adjacent sequence — honest
    known-or-nothing, exactly as any other sequence (e.g. prime gaps: OEIS-known,
    no closed form). This engages the data MatyOS legitimately can; it says nothing
    about the conjecture."""
    from matyos.discovery.objects import Sequence
    from matyos.discovery.engine import DiscoveryEngine
    seq = _adjacent_sequence(key, upto)
    records = DiscoveryEngine(min_score=0.0).records([Sequence.of(seq, name=f"{key}_adjacent")])
    return {"problem": REGISTRY[key].name, "adjacent_sequence": seq[:20],
            "n_terms": len(seq), "candidates": records[:3],
            "note": "exploration of adjacent data; NOT progress on the conjecture"}
