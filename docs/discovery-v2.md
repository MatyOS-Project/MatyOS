# MatyOS v2 — the discovery engine

> **Status: scaffold.** This document describes a direction and a four-component
> architecture. The code under `matyos/discovery/` implements the *shape* of that
> architecture with one honest end-to-end toy loop. It is not yet a working
> discovery system, and everything labelled `STUB` in the code is a placeholder.

## Where this sits relative to v1

A note on framing, because an earlier draft overstated it. MatyOS v1 is **not** a
dead "proof-syntax DSL". It is a real, sound, dependently-typed proof kernel
(inductive types, recursors, propositional equality, an impredicative `Prop`, a
three-valued `realistic` logic) with 300+ passing tests. That kernel is not being
thrown away. v2 is an **additive** second track that reuses v1 as one of its
verification backends — the optional formal-proof handoff in component 4 — not a
replacement for it.

What v1 does *not* attempt, and v2 does, is **generation**: producing genuinely new
mathematical objects, patterns and conjectures, rather than checking proofs of
statements a human already posed.

## Goal

MatyOS v2 is a **mathematical discovery engine**. The milestone it aims at is the
one Terence Tao points to for AI in mathematics: not solving famous open problems,
but surfacing ideas no one has seen before.

It sits between two existing lineages:

- **Automated conjecturing** — Ramanujan Machine, AM/Eurisko, Graffiti: generate
  new true-but-unproven statements.
- **Search-and-evaluate discovery** — FunSearch, AlphaEvolve: LLM + evolutionary
  search + a scoring function generate new constructions and algorithms.

The intended differentiator is **cross-domain resonance** as a first-class
generative move — taking structure from one domain and re-expressing it in another
to see whether the translation yields something nontrivial — run as part of the
core loop rather than bolted on.

## Architecture — four components

The loop is: **seeds → generate → score → verify → shortlist.**

### 1. Object Representation Layer — `objects.py`

A generic vocabulary for mathematical *objects* (sequences, formulas, graphs,
operators, structures), not proof terms. `MathObject` is the base; the scaffold
implements `Sequence` and `Formula`. Each object records a `provenance` trail so
the shortlist can explain where a candidate came from.

### 2. Generator / Mutator — `generator.py`

Produces candidates from existing objects. Within-domain moves (compose,
generalize, specialize) plus the differentiator, `cross_domain_transfer`. The
scaffold implements one transfer direction end to end — `sequence -> formula` via
order-2 linear-recurrence detection — enough to make the mechanic real. Pure
geometric sequences make that fit singular, and the code returns no transfer rather
than a wrong one; that honesty is deliberate.

### 3. Interestingness Scorer — `scorer.py`

The hardest piece, and the one that cannot be fully solved — that *is* Tao's point.
So the scorer does not judge; it computes reproducible **proxies** and returns a
breakdown for a human to read:

- **numerical anomaly** — does a characteristic number land on a known constant?
  (real, high-precision match; the honest PSLQ version is a `STUB`)
- **structural novelty** — irreducible to a trivially simpler object? (crude)
- **resonance** — did this object arrive by a cross-domain transfer that survived?
  (real, read from provenance)
- **surprise** — deviation from a random-baseline null model (crude placeholder)

### 4. Cheap verification + human triage — `verify.py`, `triage.py`

Before anything is surfaced: recompute the anomaly at higher precision (guards
against short-prefix coincidences), check for prior art (an offline OEIS-style
table stands in for the real networked OEIS/literature search — a `STUB`), and
optionally hand off to a proof assistant (`STUB`). The output is a short **ranked
shortlist for a human**, never an autonomous claim.

## The toy loop

`matyos discover` seeds a few integer sequences.
The signal to watch is real, not scripted: the Fibonacci prefix cross-domain
-transfers into its closed recurrence rule, whose consecutive-term ratio the scorer
detects as a numerical anomaly matching the golden ratio φ; verification confirms
the match survives a 60-term prefix; triage ranks it first. The `evens` and `pow2`
seeds show the honest negative cases (arithmetic ratio → 1, no constant match;
geometric → singular fit, no transfer).

## Explicitly out of scope (for now)

- Competing with Lean/mathlib as a proof kernel (v1's job, and a decade-scale one).
- Solving named open problems (a separate proof-search mission).
- Real PSLQ, networked OEIS/literature search, and Lean handoff — all `STUB`s with
  stable signatures, left for the next iteration.
- The evolutionary outer loop (feed survivors back as seeds under a budget). The
  seam for it is `DiscoveryEngine.step`.

## Map from the old "Discovery Engine" concepts

The earlier concept notes (Structure Pressure, Cross-Domain Resonance, Conjecture
Breeding) map onto components 2 and 3: they were always aimed at this goal, just not
implemented as the core mechanic. The v1 proof-syntax (`theorem`/`proof`) survives
as an optional output format for candidates that reach the proof-attempt stage.
