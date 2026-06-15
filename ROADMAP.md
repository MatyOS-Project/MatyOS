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

…both serving one product loop:

---

## The scientific-method workflow (the product north star)

MatyOS is organised around how mathematics is actually *done* — the scientific
method — and turns each step into first-class syntax, files, and tooling:

```
   ┌─ hypothesise ──┐
   │  .hyp           │   assume / conjecture  (epistemically REALISTIC)
   ▼                 │
   state  ─ .thm ─────▶  a precise proposition (an open obligation)
   ▼                 │
   experiment ─ .test ▶  computational checks the kernel runs
   ▼                 │
   prove  ─ .prf ─────▶  a kernel-checked derivation  → CERTIFIED
   ▼                 │            (or CONDITIONAL if it rests on a conjecture)
   bundle ─ theory ───▶  a verified body of knowledge
   ▼                 │
   seal  ─ .matyos ──▶  a compressed, self-describing archive (a *sigma of files*)
   └─ distribute / build on ─┘
```

The hard line MatyOS draws — and tracks **transitively** — is *certified* (rests
on nothing unproven) vs *conditional / realistic* (rests on an open conjecture).
This is the bridge to LLM-driven mathematics: a model may hypothesise and
conjecture freely, while the system always reports, honestly, what is proven
versus merely believed.

**Status:** the loop exists end-to-end (Phase P, done). Remaining workflow phases:

- **W1 — richer tests & evidence** *(next on this track)*: tests that attach
  numeric/sample evidence and confidence to a conjecture; a per-conjecture
  evidence log.
- **W2 — discharge queue**: surface the highest-leverage open conjectures (those
  the most certified results depend on) for a human/LLM to attempt next.
- **W3 — theory registry & `import`**: let a `.matyos` theory depend on and build
  on other sealed theories; versioned, hash-pinned.
- **W4 — LLM conjecture↔proof loop**: an LLM proposes conjectures/proofs, the
  kernel certifies or refutes, and the realistic status updates automatically
  (joins the Realistic track R2–R3 and the LLM loop C7).

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

### Phase C1b — Propositional equality & the J rule ✅ (done)
- [x] Propositional equality `Eq : A -> A -> Type` with `refl`, and its
      eliminator (the based J rule) + its ι-rule `J A a P d a (refl) ==> d`.
      → `kernel/equality.py` (also derives `cong`).
- [x] **Milestone:** `∀ n, n + 0 = n` proved by induction, kernel-checked.
      → `kernel/demo_equality.py`.
- [ ] (follow-up) a general indexed-inductive engine that *derives* Eq/J rather
      than declaring them as primitives.

### Phase C1c — Well-formedness guards ✅ (done)
- [x] **Strict positivity** check (rejects non-well-founded inductives such as
      `Bad = mk (Bad -> Bad)`). → `kernel/inductive._check_positivity`,
      `kernel/demo_positivity.py`.
- [x] **Termination** holds by construction: the only recursion is via
      datatype recursors (structurally terminating); there is no general `fix`.
- [ ] (follow-up) a structural-recursion checker once surface-level `def`
      with general recursion exists (C3+).

### Phase C2a — Definitions & δ-reduction ✅ (done)
- [x] `define(name, type, body)` — type-checks the body against the annotation,
      then `Const(name)` δ-reduces to the body. → `kernel/core.define`,
      `kernel/demo_definitions.py` (`double 3 = 6`; the `n+0=n` theorem stored
      as a checked definition; bogus defs rejected).

### Phase C2b — Impredicative `Prop` ✅ (done)
- [x] `Prop` sort (`Prop : Type0`) with the impredicative product rule (imax):
      a `Pi` into `Prop` stays in `Prop`; otherwise predicative `max`.
      → `kernel/core.py`, `kernel/demo_prop.py` (`False := ∀P:Prop,P : Prop`;
      `not`, `absurd`/ex-falso type-check; predicative `Type` contrast shown).
- [ ] (optional, later) proof irrelevance for `Prop`.

### Phase C2c — Universe polymorphism
- [ ] Level variables + constraints so definitions/inductives work at any
      universe (removes the current fixed `Type0` motive limit). Intricate;
      to be done carefully (unsoundness risk if rushed).
- **Milestone:** a small `Prelude` (logic connectives as inductives, `Eq` lemmas).

### Phase C3 — Surface syntax & a real parser ✅ (done)
- [x] Tokenizer + parser for the proof language → kernel terms.
      Terms: `fun`, `forall`, dependent `(x:A) -> B`, arrows, application,
      `Type[u]`, `Prop`. Commands: `def`, `axiom`, `inductive`, `example`,
      `check`, `eval`. → `kernel/surface.py`.
- [x] Proofs now live in text files: `kernel/library/arith.elk` declares `Nat`,
      defines `add` (`eval` shows 2+3=5), and proves `∀ n, n+0=n` (`example`
      reports QED) — no Python AST.
- [ ] (follow-up) named/round-trippable pretty-printer (kernel printer still
      shows de Bruijn-derived names like `x0`); notation/sections; indexed
      `inductive` syntax (so `Eq` can be declared in-language rather than as a
      prelude primitive).

### Phase P — Project system & the scientific method ✅ (done)
The packaging/UX layer that makes MatyOS usable for real bodies of work.
- [x] Scientific-method commands: `theorem` / `proof` / `hypothesis` /
      `conjecture` / `test` (`matyos/frontend/surface.py`).
- [x] **Transitive assumption tracking** — a result is *certified* only if it
      depends on no open conjecture, else *conditional / realistic*; tracked
      through chains of lemmas (`core.const_names`).
- [x] File types `.thm` / `.prf` / `.hyp` / `.test` / `.elk`; a *theory* =
      a sub-directory; projects run in scientific-method order with a status
      report (`matyos/project/engine.py`).
- [x] **Compression / sealing**: `matyos build` seals a *completed* project
      into a compressed `.matyos` archive (zip) embedding `MANIFEST.json` +
      `REPORT.txt`; `matyos info` reads the manifest; `check` re-verifies.
- [x] Black-and-white icon set for every file type (`assets/icons`, `Σ ∀ ∎ ∃ ✓ λ`).
- [ ] (follow-up) a package registry so theories can `import` other sealed
      `.matyos` theories; colour icon pass.

### Phase C4 — Elaboration
The largest core layer.
- [ ] Metavariables + higher-order pattern unification.
- [ ] Implicit arguments and instance/`typeclass` resolution.
- [ ] Coercions, unification hints, error localization.
- **Milestone:** write proofs without spelling out every type argument.

### Phase C5a — A first tactic engine ✅ (done)
Proofs as scripts (`by … qed`) instead of raw terms. The tactic engine is
**untrusted** — it only builds a term the kernel re-checks, so soundness is
preserved no matter how clever (or buggy) a tactic is.
- [x] `intro`, `exact`, `assumption`, `refl` over a (linear) goal.
      → `matyos/frontend/tactics.py`, `examples/proofs/tactics.elk`.

### Phase C5b — Tactics with sub-goals (needs C4)
- [ ] A proper proof state (goal stack + context + metavariables).
- [ ] `apply` (generates sub-goals), `induction`, `cases`, `rewrite`.
- [ ] Automation: `simp` (rewriting), linear-arithmetic decision procedure,
      an SMT/`omega`-style bridge.
- [ ] Tactics writable *in* the language (reflection / metaprogramming).

### Phase C6 — The library (the moat)  ← *now growing*
- [x] Equality toolkit derived from `J`: `symm`, `trans`, `cong`, `subst`
      (`stdlib/eq.elk`).
- [x] First real arithmetic theorems, **certified** by induction:
      `add_zero_r`, `add_succ_r`, and **`add_comm` (commutativity of +)** —
      `examples/projects/arithmetic` (a sealed theory).
- [x] **ℕ is a certified commutative semiring** (`stdlib/nat.elk`): `+` and `×`
      with associativity & commutativity of both, identities `0`/`1`
      (`add_zero_l/r`, `mul_one_l/r`), the annihilator (`mul_zero_l/r`), and
      distributivity (`mul_distrib_r`) — every law proved by induction.
- [x] **Ordering `≤`** (`stdlib/nat.elk`): `le m n := (leb m n = true)` with
      `le_zero`, `le_refl`, `le_succ`, and **`n ≤ n + m`** — certified.
      (`le_trans`/`le_antisymm` need Bool case-analysis or an indexed `le`;
      pending.)
- [ ] Subtraction, `Int`/`Nat`-division, then number-theory (divisibility,
      primes) — and indexed inductives so `≤` can be a proper `Prop` family.
- [ ] Foundations: logic, sets, relations, functions, orders.
- [ ] Numbers: ℕ, ℤ, ℚ, ℝ (Cauchy/Dedekind), basic analysis.
- [ ] **Bootstrapping strategy** (this is how you avoid the 6-year wall):
      LLM-driven **autoformalization** — translate textbook/Lean/Mathlib
      statements into El, then have the LLM+tactics close the proofs, with the
      kernel as the gatekeeper. Library growth becomes a *generation* problem,
      not a *typing* problem.

### Phase C7 — Tooling & the LLM loop (the wedge)  ← *started*
- [x] **Machine-readable output**: `matyos check --json` emits every theorem's
      status (certified / conditional / open), its conjecture dependencies,
      tests, and per-command events as JSON — so a tool or LLM consumes exactly
      what the kernel sees, no text-scraping. (`matyos/cli.py`.)
- [ ] REPL + LSP (hover types, goals-on-cursor, errors).
- [ ] Live **proof-state** serialization (open goals + context) for tactic mode.
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
