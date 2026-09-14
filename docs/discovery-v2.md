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

A generic vocabulary for mathematical *objects* (sequences, formulas, series,
continued fractions, graphs…), not proof terms. `MathObject` is the base; the
engine implements `Sequence`, `Formula`, `Series` (a convergent sum → a constant),
and `ContinuedFraction` (b0 + a1/(b1 + a2/(b2 + …)) → a constant). Each records a
`provenance` trail so the shortlist can explain where it came from.

**Continued-fraction search (`cf.py`) — the Ramanujan-Machine move.** `cf.search`
enumerates simple polynomial continued fractions, evaluates each to high
precision, and hunts a closed form for the value *or its reciprocal* (many CFs
converge to a rational multiple of 1/constant, e.g. 4/π). Hits are CF identities
for constants — the one part of MatyOS whose output could in principle be new.
It is a **heavy batch job** (~seconds per CF: a high-precision evaluation plus two
PSLQ hunts), bounded by `max_scan`/`max_hits`; run it as a background search, not
interactively. Its PSLQ basis is deliberately broad (π, π²–π⁴, e, √2–√13, ln2/3/5,
γ, Catalan, ζ(3), ζ(5), ζ(7)), guarded by the sparsity + significance gates so the
larger basis does not manufacture numerology.

### Driving the search with a model (`reasoner.py`)

The loop decides what to try next through a **Reasoner**. The default
(`MutationReasoner`) uses fixed mutations — no model. To let **Claude or any other
LLM** drive, pass a `CallbackReasoner(fn)`: each round the engine hands `fn` the
state (seeds tried, closed forms found, mystery constants) and `fn` returns the
next seeds — as a list, or as free text the engine parses. `prompt_for(context)`
renders that state into a ready prompt. MatyOS never hardcodes a provider, so it
works with Claude, GPT, or a local model — you supply the function that calls
yours. Inside Claude Code, a session can also drive it from outside by calling the
MCP `discover` tool round after round.

**Graphs (`graph.py`) — a domain beyond numbers (the Graffiti move).** Instead of
a formula for a sequence, the objects of interest are *inequalities between graph
invariants*. `graffiti_search` computes invariants over a spread of small connected
graphs and returns the tight inequalities `A(G) <= B(G)` that held on every one —
candidate theorems (e.g. it rediscovers `radius <= diameter` and `min_degree <=
avg_degree <= max_degree`). They hold on the sample; proving them for all graphs is
a human/Lean job. The invariant set is broad: combinatorial ones (order, size,
degrees, triangles, diameter, radius, independence / clique / chromatic /
vertex-cover numbers, **domination number, matching number, vertex- and
edge-connectivity, degeneracy, girth**) are pure Python; **spectral invariants**
(spectral radius, graph energy, algebraic connectivity / Fiedler value, Laplacian
spectral radius) use mpmath eigenvalues when available — with these the search
rediscovers the classic bracket `avg_degree <= spectral_radius <= max_degree` and
`laplacian_spectral_radius <= order`.

**The novelty filter (`known.py`) and the honest loop.** Surfacing a tight bound is
cheap; knowing whether it is *new* is the hard part. `classified_search` tags each
inequality `known` (an established theorem in a curated DB), `derived` (implied by
known bounds through a transitive-closure chain, which is reported), or `candidate`
(not implied by anything MatyOS knows — a lead, never a novelty *claim*). The
honest workflow around a candidate is: **stress-test** it on hundreds of random and
structured graphs (a bound tight on the small sample often breaks — those false
conjectures are refuted with a witness graph and their witnesses folded back into
the sample), then **literature-check** and **attempt a proof**; a proven bound is
added to the DB so the filter sharpens over time. This loop closed once end to end
on `radius <= vertex_cover_number` (surfaced → stress-tested → proven; see
`docs/conjectures/radius-le-vertex-cover.md`).

### 2. Generator / Mutator — `generator.py`

Produces candidates from existing objects. Within-domain moves (compose,
generalize, specialize) plus the differentiator, `cross_domain_transfer`. Two
transfer hops are built: `sequence -> formula` (order-2 linear-recurrence
detection) and `formula -> series` (the reciprocal series `sum 1/a(n)`, whose
value is then hunted for a closed form). So a number-sequence can become a rule,
and a rule can become a constant — genuinely crossing domains. Pure geometric
sequences make the recurrence fit singular, and the code returns no transfer
rather than a wrong one; that honesty is deliberate.

*Mysteries are kept.* A series that converges to a **stable constant with no
known closed form** is scored by a dedicated `mystery` signal (weighted alongside
anomaly and resonance), so unknown constants are surfaced rather than filtered —
that is where new discoveries hide. Stability is required (the value must agree at
two precisions) so numerical noise is not mistaken for a constant. Such a find is
labelled *mystery* with novelty *unknown* and truth REALISTIC.

### 3. Interestingness Scorer — `scorer.py`

The hardest piece, and the one that cannot be fully solved — that *is* Tao's point.
So the scorer does not judge; it computes reproducible **proxies** and returns a
breakdown for a human to read:

- **numerical anomaly** — does a characteristic number land on a known constant?
  (real: PSLQ integer-relation detection over a constant basis, via mpmath —
  recovers closed forms like the golden ratio (1+sqrt5)/2)
- **structural novelty** — irreducible to a trivially simpler object? (crude)
- **resonance** — did this object arrive by a cross-domain transfer that survived?
  (real, read from provenance)
- **surprise** — deviation from a random-baseline null model (crude placeholder)

### 4. Cheap verification + human triage — `verify.py`, `triage.py`

Before anything is surfaced: recompute the anomaly at higher precision (guards
against short-prefix coincidences), **refute** it — derive the closed form from a
near window and check it still predicts the invariant far beyond it, so a
short-prefix coincidence dies here — check for prior art (a **live OEIS query**,
falling back to a small offline table with no network), and **hand off to Lean**
— emit a Lean 4 theorem statement (with `sorry`) to verify against **mathlib**,
and report whether a Lean toolchain is present. MatyOS *states* the conjecture;
proving it is Lean+mathlib's job, never MatyOS's. Every surviving find carries a **`realistic`
label** from `matyos/logic` — FALSE if refuted, REALISTIC if found but unproven,
TRUE only if proven — plus a separate novelty flag (known vs new). The output is a short **ranked
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
- Literature search beyond OEIS — still a `STUB`. The Lean handoff now emits a
  statement to check against mathlib, but does not autoformalize the exact term
  for every domain, nor auto-prove — that (autoformalization) stays hard and human.

The iterated loop **is** built now: `DiscoveryEngine.loop` runs rounds, records
every find in a `CandidateStore` (deduplicated by identity), and breeds the next
seed frontier from this round's seeds while dropping anything already seen — the
novelty pressure that stops the search collapsing onto the seed. Still narrow:
breeding is by within-domain mutation, so it explores a neighbourhood, not the
whole space; broader object domains and real cross-domain transfer come next.

## Map from the old "Discovery Engine" concepts

The earlier concept notes (Structure Pressure, Cross-Domain Resonance, Conjecture
Breeding) map onto components 2 and 3: they were always aimed at this goal, just not
implemented as the core mechanic. The v1 proof-syntax (`theorem`/`proof`) survives
as an optional output format for candidates that reach the proof-attempt stage.
