# MatyOS — the honest ladder toward harder problems

This document answers a question people ask: *can MatyOS attack famous unsolved
problems — the Riemann Hypothesis, Goldbach, twin primes, Collatz?*

## The wall, stated first

**No. MatyOS cannot and will not target any famous open problem, and this is a
permanent boundary, not a tuning gap.** Those problems need analytic and
number-theoretic machinery MatyOS has none of; there is no way even to *represent*
them in the system — no input format, no mechanism, the wrong class of tool. Even
far larger systems (e.g. Google's AlphaProof) only solve *competition* problems
that already have answers, not open research problems. Anyone claiming a tool like
this "solves Riemann" is wrong, and repeating the claim destroys credibility. What
follows is only the *reachable* space, and it stops well short.

## The reachable ladder

| Rung | What it means | Status |
|---|---|---|
| **A** | Rediscover known bounds/identities; auto-prove *easy* goals (Lean + mathlib) | **Done** |
| **B** | Surface a genuinely-new *small* conjecture — a true tight bound not in the literature | Possible, low rate |
| **C** | Prove a surfaced conjecture (paper, and ideally machine-checked) | Done once, for a small/elementary bound |
| **D** | Improve a *known numeric record* on one narrow combinatorial problem (FunSearch / AlphaEvolve style) | Aspirational ceiling; not attempted |
| — | **Famous open problems (Riemann, …)** | **Not a target — ever** |

Rung C was reached once: `radius <= vertex_cover_number` was surfaced by the graph
loop, stress-tested, flagged as not-in-the-knowledge-base, then proven (an
elementary, likely-folklore bound). That is the honest proof-of-concept — the
pipeline **surface → stress-test → filter → prove** works — not a claim of new
famous mathematics.

## The honesty gates (enforced at every rung)

These are what make the ladder trustworthy rather than a hype generator:

1. **Stress-test before trust.** A bound tight on a small sample is refuted on
   hundreds of random/structured graphs surprisingly often; a refuted bound is a
   *negative result*, recorded with a witness, not hidden.
2. **Novelty filter.** Every bound is tagged known / derived / candidate; MatyOS
   never calls a bound "new" on its own authority.
3. **Literature check** before treating any candidate as unrecorded.
4. **Never print "proved" / "new" / "discovered" unless earned** — Lean accepted
   the proof, or it is literature-confirmed unrecorded *and* proven.

Negative results are output. The continued-fraction "mystery" search, for example,
was measured to be noise (≈85% of continued fractions look "mysterious" because a
generic transcendental has no nice closed form) and that finding is recorded in the
code, not swept away.

## What "progress" honestly looks like

Widen the invariant/object set → more candidate bounds → run the honest workflow →
a shortlist of stress-survived, not-in-the-DB bounds → attempt proofs → fold proven
ones back into the knowledge base. If a candidate ever resists both proof and
refutation *and* is literature-confirmed unrecorded, that is a real (small) open
conjecture MatyOS produced — to be published *as a conjecture*, labelled honestly.

Rung D (beat a known record on one narrow problem) is the furthest a tool of this
kind has ever reached, and it is still not a famous problem. It would be a separate,
larger, opt-in effort. MatyOS's value is not pretending to be more than this — it is
being a machine that will not claim what it cannot back up.
