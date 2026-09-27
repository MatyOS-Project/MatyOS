# Stoqos — a calibrated model for the REALISTIC level

MatyOS uses a three-valued logic: **TRUE** (the kernel proved it), **FALSE** (a
counterexample refuted it), and **REALISTIC** (held on the evidence, but unproven).
TRUE and FALSE are decided by proof and by counterexample. Only REALISTIC is
inherently uncertain — and **Stoqos estimates that uncertainty**: given a bound
that survived the evidence, it returns a *calibrated probability that the bound is
actually true*.

Stoqos is a **scorer, never a judge.** It grades the uncertain middle; it can never
promote a claim to TRUE (the kernel's job) or demote it to FALSE (a
counterexample's job). A wrong or offline Stoqos wastes search effort; it can never
make MatyOS assert a falsehood.

## Using it

```python
from matyos.discovery import stoqos

stoqos.judge("radius <= diameter")
# Judgement(verdict='realistic', value=1.0, confidence=1.0, known=True, ...)

stoqos.judge("diameter <= radius")     # a counterexample exists in the evidence
# Judgement(verdict='false', value=None, ...)

stoqos.judge("foo <= bar")             # out of domain
# Judgement(verdict='unknown', value=None, ...)

# domain-general: score any bound from two aligned evidence value-lists
stoqos.score_evidence(lhs_values, rhs_values)   # -> P(true) in [0,1], or None if it fails

# rank a batch of graph candidates by promise (uses Jev when configured, else Stoqos)
from matyos.discovery import graph
graph.classified_search(score=True)
```

`judge()` returns one of four honest verdicts: **realistic** (committed, with a
calibrated value), **uncertain** (too close to call — abstains), **false**
(counterexample in the evidence), **unknown** (out of domain).

## How it was built (Phases 0–5)

| Phase | What | Result (held-out, measured) |
|---|---|---|
| 0 | Logistic baseline, 7 hand features | Brier 0.182 |
| 1 | Learned MLP + richer features | Brier **0.141** (−22%) |
| 2 | + invariant metadata (family, monotonicity, known-facts) | fixes known-theorem misses (κ≤δ 0.02→0.85) |
| 3 | Typed API (`judge`) with abstention | realistic/uncertain/false/unknown |
| 4 | Selective prediction | accuracy rises 0.985→0.998 as it abstains |
| 5 | Multi-domain (graphs + number sequences) | one model: graphs **0.886**, sequences **0.853** AUC |

Training labels are **kernel-grounded**: a bound is labelled *true* when it holds on
a hard verification battery and *false* when a counterexample is found. No human
opinion is injected.

## Honest limitations

- **Aggregate-calibrated, not an oracle.** Reliability holds in aggregate; a single
  score is not a verdict. Trust the ranking and the calibrated probability, never a
  lone number as truth.
- **Same-domain memorisation.** In-distribution metrics are inflated because train
  and test share the same invariant pairs; the honest numbers are the pair-disjoint
  and cross-domain ones above.
- **No zero-shot transfer.** A model trained on one domain does *not* transfer
  (graph→sequence AUC 0.358, worse than chance). Generality comes only from
  **joint multi-domain training** (Phase 5), not transfer.
- **Domain-bounded.** Validated on graph-invariant inequalities and simple
  number-sequence bounds. Outside these, treat the output as unknown.

## Relation to Jev

Jev (TypeSafe AI) is a calibrated decision *model*; REALISTIC is a *logic*. They
share one instinct — never fake certainty, put an honest number on the unknown —
but Stoqos's calibration is grounded in a **kernel** (TRUE means *proven*), which
a purely statistical model is not. `matyos.discovery.jev` will use the Jev API as
the promise-scorer when `MATYOS_JEV_API_KEY` is set, falling back to a transparent
heuristic otherwise.
