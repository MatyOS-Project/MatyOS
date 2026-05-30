# El — Roadmap to an LLM-Native Proof Assistant

> **Goal.** A from-scratch proof assistant that is competitive with Lean for
> doing mathematics, and that **LLMs can use** to analyze, conjecture, and
> prove.

## 0. Honest framing (read this first)

A proof assistant is three things, in increasing order of effort:

1. **A trusted kernel** — a small, sound type-checker for proof terms. Finite,
   hard to get *correct*, but achievable. *(We have a seed.)*
2. **Elaboration + tactics** — the large engineering layer that turns
   human/LLM-written proofs into kernel terms. Big but bounded.
3. **A mathematics library** — the Mathlib-equivalent. **This is the moat.**
   Lean's Mathlib is ~1.7M lines, ~400 contributors, ~6 years. "Doing analysis"
   *is* this library. No small team reproduces it by hand.

So "competitive with Lean for all of mathematics" is a decade-scale, community
effort. The realistic way to be *competitive in a niche soon* is to win on the
axis Lean was never designed for: **LLM-native authoring + uncertainty-aware
reasoning**, while bootstrapping the library by autoformalization rather than by
hand. This roadmap pursues the full system but front-loads that wedge.

Two parallel tracks run throughout:

- **Core track (C):** the trusted kernel growing to Lean-class expressiveness.
- **Realistic track (R):** the `realistic`/uncertainty layer — our
  differentiator — kept *above* the trusted core so it never threatens
  soundness.

---

## Core track

### Phase C0 — Foundations ✅ (done)
- [x] Dependent type theory kernel: universes, Π-types, λ, application,
      de Bruijn terms, normalization, definitional equality, `infer`.
      → `kernel/core.py`, `kernel/demo.py` (checks identity/K/MP/composition,
      rejects ill-typed terms).
- [x] (Auxiliary) sound propositional checker — a teaching artifact, not the
      path to Lean. → `compiler/proof_checker.py`.

### Phase C1a — Non-indexed inductive types & recursors ✅ (done)
The step from "logic puzzles" to mathematics.
- [x] Global environment + `Const` terms in the kernel.
- [x] Inductive declarations with parameters (`Nat`, `Bool`, `List`).
- [x] Auto-generated recursors/eliminators (induction principles) with
      dependent motives.
- [x] ι-reduction (recursor computation) wired into normalization.
      → `kernel/inductive.py`, `kernel/demo_inductive.py` computes
      `add 2 3 = 5`, `mul 3 4 = 12`, `not (not true) = true`.

### Phase C1b — Indexed families & propositional equality  ← **next**
- [ ] Indexed inductive families (constructor results may fix indices).
- [ ] Propositional equality `Eq : A -> A -> Type` with `refl`, and its
      eliminator (the J rule) + its ι-rule.
- [ ] **Milestone:** prove `∀ n, n + 0 = n` by induction, kernel-checked.

### Phase C1c — Well-formedness guards (before trusting at scale)
- [ ] **Strict positivity** check (reject non-well-founded inductives).
- [ ] **Termination / structural-recursion** check for recursor-free `def`s.
      (Until then, only recursor-based definitions are admitted, which are
      terminating by construction.)

### Phase C2 — Definitions, environment, reduction
- [ ] A global environment of named definitions/axioms.
- [ ] δ-reduction (unfolding definitions) and `let`.
- [ ] Universe polymorphism; an impredicative `Prop` (à la Lean), done soundly.
- **Milestone:** a small `Prelude` (logic connectives as inductives, `Eq` lemmas).

### Phase C3 — Surface syntax & a real parser for the proof language
- [ ] Concrete syntax for `def/theorem/inductive`, notation, sections.
- [ ] Replace the legacy `El` proof grammar; keep imperative El separate.
- [ ] A pretty-printer that round-trips with the parser.

### Phase C4 — Elaboration
The largest core layer.
- [ ] Metavariables + higher-order pattern unification.
- [ ] Implicit arguments and instance/`typeclass` resolution.
- [ ] Coercions, unification hints, error localization.
- **Milestone:** write proofs without spelling out every type argument.

### Phase C5 — Tactics & metaprogramming
- [ ] A tactic monad over proof state (goals + context + metavariables).
- [ ] Core tactics: `intro`, `apply`, `exact`, `induction`, `cases`,
      `rewrite`, `refl`, `assumption`.
- [ ] Automation: `simp` (rewriting), a decision procedure for linear
      arithmetic, an SMT/`omega`-style bridge.
- [ ] Tactics writable *in* the language (reflection / metaprogramming).

### Phase C6 — The library (the moat)
- [ ] Foundations: logic, sets, relations, functions, orders.
- [ ] Numbers: ℕ, ℤ, ℚ, ℝ (Cauchy/Dedekind), basic analysis.
- [ ] **Bootstrapping strategy** (this is how you avoid the 6-year wall):
      LLM-driven **autoformalization** — translate textbook/Lean/Mathlib
      statements into El, then have the LLM+tactics close the proofs, with the
      kernel as the gatekeeper. Library growth becomes a *generation* problem,
      not a *typing* problem.

### Phase C7 — Tooling & the LLM loop (the wedge)
- [ ] REPL + LSP (hover types, goals-on-cursor, errors).
- [ ] **Machine-readable proof state**: serialize goal/context/errors as JSON
      so an LLM sees exactly what the kernel sees.
- [ ] **Proof-search harness**: LLM proposes term/tactic → kernel verifies →
      feedback → retry (best-first / MCTS over tactic states).
- [ ] **Corpus + training**: mine (statement, proof, state-transition) data
      from El itself; expert-iteration / RL with the kernel as the reward
      signal (the verifier is automatic ground truth).
- **Milestone:** an LLM closes a non-trivial library lemma end-to-end, verified
  by the kernel, with no human term-editing.

---

## Realistic track — first-class uncertainty

The differentiator. Lean has no notion of "probably true / not yet known".
LLM-driven math *lives* in that space. We make it rigorous and, crucially, keep
it from corrupting the trusted kernel.

### Phase R0 — Rigorous 3-valued semantics ✅ (done)
- [x] Kleene (K3) and Łukasiewicz (Ł3) truth tables for `true/false/realistic`,
      validity, entailment, truth tables. → `compiler/realistic_logic.py`.
- [x] Demonstrated landmark results: excluded middle and non-contradiction are
      *not* valid with a `realistic` atom; `P→P` separates K3 (invalid) from
      Ł3 (valid). Choice of semantics is now an explicit, consequential setting.

### Phase R1 — Wire it in & generalize
- [ ] Replace the legacy ad-hoc `realistic` handling in the imperative
      interpreter (`system/builtin_functions/main.py` currently *raises* on
      `realistic and/or`) with this engine.
- [ ] Generalize the third value to **fuzzy [0,1]** (degrees of truth) and to a
      **probabilistic** reading (confidence), selectable per program.
- [ ] Decide and document the default semantics (recommend Kleene for
      "ignorance", Ł3/fuzzy for "degree").

### Phase R2 — The epistemic layer over the kernel (key idea)
Keep the trusted kernel classical/constructive and **sound**. Add an *outer*
layer the kernel never trusts:
- [ ] First-class **`conjecture`**: a proposition asserted as `realistic` with
      attached **evidence** (numeric checks, examples, an LLM's argument) and a
      **confidence**.
- [ ] A clear status lattice: `conjectured (realistic)` → `proof attempted` →
      `kernel-certified (true)` / `refuted (false)`.
- [ ] Proofs may *cite* conjectures, but any theorem depending on an
      un-discharged conjecture is itself marked `realistic` and traceable — the
      kernel certifies only the conditional `conjectures ⟹ goal`.
- **Why it matters for LLMs:** the model can reason fluidly with plausible
  lemmas (as humans do), while the system tracks exactly what is *proven* vs
  *believed*, and what must still be discharged. This is the natural interface
  between informal LLM reasoning and formal verification.

### Phase R3 — Uncertainty-aware automation
- [ ] Tactics that propagate confidence/evidence and flag where a `realistic`
      assumption was used.
- [ ] A "discharge queue": surface the highest-leverage conjectures for the LLM
      to attempt to prove next.
- [ ] Optional probabilistic/fuzzy goals for applied/analysis-flavored work.

---

## Minimum Viable Competitor (the near-term target)

Don't aim at "all of Lean" first. Aim at a coherent slice you can actually win:

> **El v0.5:** kernel + inductive types (C0–C2) + a tactic layer (subset of C5)
> + the LLM proof-search loop (C7) + the conjecture/realistic layer (R2), over a
> **small but real** library (ℕ, lists, basic algebra). The pitch: *the proof
> assistant where an LLM can conjecture-with-confidence and prove, and you can
> always see what's certified vs believed.*

That is a defensible, demoable niche long before a Mathlib-scale library exists.

---

## Effort & sequencing (honest)

- C0 ✅ · R0 ✅ — done.
- C1 (inductive types): the next concrete build; high leverage, bounded.
- C2–C3: medium; unlocks real definitions and syntax.
- C4–C5: the heavy core engineering (elaboration + tactics).
- R1–R2: can proceed in parallel; R2 is the differentiator — prioritize once
  C5 tactics exist.
- C6: continuous, library-forever; bootstrap via C7 autoformalization.
- C7: start the serialization + search harness early (it pays for itself in
  testing and is the whole LLM thesis).

## Non-negotiables
1. **Kernel soundness is sacred.** Everything (elaboration, tactics, realistic,
   LLM output) must reduce to terms the small trusted kernel checks. `realistic`
   never enters the trusted core.
2. **No silent "assumed proven".** Every theorem's status is exactly one of
   proven / refuted / realistic(conjectural) / open — and always honest.
3. **Machine-first ergonomics.** If the LLM can't see the proof state and the
   error precisely, the whole thesis fails. Build serialization with the core.
