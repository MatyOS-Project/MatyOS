# Hard problems — an honest engagement layer (DESIGN PREVIEW)

> **This is not a solver and never becomes one.** MatyOS cannot prove the Riemann
> Hypothesis, Goldbach, the Twin Prime conjecture, or Collatz, and no version of
> this layer will claim to. Its purpose is to let MatyOS *engage honestly* with
> these problems at the level it genuinely can, and to refuse — structurally — to
> overstate. Every record this layer produces carries a `provable_by_matyos:
> false` flag for the conjecture itself.

## What "ready for a hard problem" honestly means

For each famous problem, MatyOS provides four honest capabilities and nothing more:

1. **State** — a formal Lean 4 statement of the conjecture, checked to typecheck
   against mathlib (via the existing `lean.try_prove`/handoff plumbing). The body
   is `sorry`. MatyOS states; it does not prove.
2. **Verify finite** — compute/verify the conjecture on a bounded range (Goldbach
   for even numbers up to N; twin pairs below N; Collatz trajectories to 1 below
   N). This is *evidence*, explicitly labelled "finite check, not a proof."
3. **Explore adjacent data** — run the real discovery engine on the sequences the
   problem generates (Collatz stopping times, Goldbach partition counts, prime/gap
   sequences), reporting the honest known-or-nothing outcome (as with prime gaps:
   OEIS-known, no closed form).
4. **Track** — record the genuine mathematical state: major partial results and the
   mathlib formalization status, so the workspace reflects reality, not hope.

## The registry (per-problem honest content)

Each entry is data for a `matyos/problems/` module: `name`, `lean_statement`,
`known_results`, `matyos_can`, `matyos_cannot`, `status`.

### Riemann Hypothesis
- **Lean statement:** `RiemannHypothesis` is already stated in mathlib
  (`Mathlib.NumberTheory.LSeries.RiemannZeta` neighbourhood) — non-trivial zeros of
  ζ have real part ½. MatyOS re-exports/checks it; proof body stays open.
- **Known:** ζ defined; ~10^13 zeros verified on the critical line numerically; RH
  equivalent to bounds on π(x); still open since 1859.
- **MatyOS can:** state it in Lean; nothing on the analytic object itself (no ζ,
  no complex analysis in the engine).
- **MatyOS cannot:** represent ζ, test the zero condition, or make any progress.
  **This is the least-reachable of the four — engagement is essentially "state + track" only.**

### Goldbach (strong)
- **Lean statement:** `∀ n : ℕ, Even n → 2 < n → ∃ p q, p.Prime ∧ q.Prime ∧ n = p + q`.
- **Known:** verified to 4×10^18; Chen's theorem (n = p + P₂); ternary Goldbach
  proved (Helfgott 2013).
- **MatyOS can:** state in Lean; **verify** the finite range (real, cheap); explore
  the Goldbach-partition-count sequence with the discovery engine.
- **MatyOS cannot:** prove the ∀ statement.

### Twin primes
- **Lean statement:** `∀ N : ℕ, ∃ p, N < p ∧ p.Prime ∧ (p + 2).Prime`.
- **Known:** infinitude open; Zhang 2013 → bounded gaps; Maynard/Polymath → gap ≤ 246.
- **MatyOS can:** state in Lean; **enumerate** twin pairs below N; explore the
  twin-gap sequence.
- **MatyOS cannot:** prove infinitude.

### Collatz (3n+1)
- **Lean statement:** `∀ n : ℕ, 0 < n → ∃ k, collatz^[k] n = 1` (with `collatz`
  defined as n/2 if even, 3n+1 if odd).
- **Known:** verified to ~2^69; Tao 2019 (almost all orbits reach small values);
  open in general.
- **MatyOS can:** define `collatz`; **verify** trajectories to 1 for all n < N;
  explore the stopping-time sequence with the discovery engine.
- **MatyOS cannot:** prove it for all n.

## Built-in honesty (structural, not just prose)

- Every problem record hard-codes `provable_by_matyos = False` for the conjecture.
- The `verify_finite` results are typed as `FiniteEvidence`, whose repr always
  reads "checked n < N; NOT a proof."
- The Lean statements are emitted with `sorry` and pass through the same
  `realistic`-label path as any other conjecture: status REALISTIC (open), never TRUE.
- No function in this layer can return "proved" for a conjecture-level statement;
  only the finite/adjacent sub-results can be confirmed.

## Architecture for the future (the real, ambitious build)

The honest system, in dependency order — **the proving leg first**, as you asked:

1. **Proving leg (start here).** Deepen `lean.try_prove`: beyond the tactic ladder,
   add a mathlib-lemma search and multi-step proof attempts, a proof cache, and a
   result type that records *which* mathlib lemmas closed a goal. This is the
   highest-value lever: it turns "state a conjecture" into "prove the reachable
   ones," machine-checked.
2. **Object/representation layer** — the generic `MathObject` grows to carry formal
   (Lean) statements alongside numeric data, so discovery output and formal
   statement are one object.
3. **Conjecture generation** — more domains/invariants feeding candidates (the work
   already underway in graphs), each auto-emitting a formal statement.
4. **Hard-problems workspace** — this registry, wired to (1)–(3): state, verify
   finite, explore adjacent, track. Honest ceiling enforced throughout.
5. **Rung D (optional, later)** — a scored search to improve *one* known numeric
   bound on a narrow problem. The furthest honest reach; still not a famous proof.

## The line that does not move

This layer makes MatyOS a place to *hold* hard problems honestly — state them,
poke at their finite/adjacent structure, and track the real mathematics. It is a
mathematician's honest workbench, not an oracle. If a future version ever prints
"proved" against one of these four conjectures, that is a bug, not a breakthrough.
