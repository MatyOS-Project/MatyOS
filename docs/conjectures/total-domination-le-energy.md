# total_domination_number(G) ≤ energy(G) — RESOLVED (known corollary)

**Status: resolved / known.** Surfaced by MatyOS's widened graph loop (with spectral
invariants enabled) as a candidate, then settled by a literature check as a true
theorem — a corollary of two established inequalities. Not new, but now honestly
accounted for, and promoted to the `known` DB. MatyOS never claimed it as a
discovery; the resolution is a confirmed chain, not a fabricated proof.

## Resolution

`γ_t(G) ≤ energy(G)` follows from two known theorems:

1. **`γ_t(G) ≤ 2·ν(G)`** — a maximum matching is maximal, and the vertex set of a
   maximal matching is a total dominating set, so `γ_t ≤ 2ν`.
2. **`E(G) ≥ 2·ν(G)`** — the well-known lower bound of graph energy by the matching
   number (Gutman-era; `E(G) ≥ 2μ(G)`), verified in the literature.

Hence `γ_t ≤ 2ν ≤ E`. ∎ (The factor of 2 means it is not a chain of invariant-name
`≤` edges, so it is listed directly in `known.py` rather than derived.)

Notation: `γ_t(G)` = total domination number (smallest `S` such that every vertex,
`S` included, has a neighbour in `S`); `ν(G)` = matching number; `E(G)` = graph
energy = sum of the absolute values of the adjacency eigenvalues.

## Evidence

- 0 violations across 443 graphs (random + paths/cycles/stars/Petersen/grids/cube).

Both links held on 426/426 test graphs, and both are confirmed theorems in the
literature — so this is a settled corollary, not an open lead.

## Literature

The direct inequality `γ_t ≤ E` was not located as a stated theorem (the
energy/domination literature mostly addresses other quantities: *dominating energy*
`E_D(G)`, adjacency-rank bounds `γ_t ≤ n − m_G(0)` (Abiad et al. 2023), square
energies). But its two ingredients are standard: `γ_t ≤ 2ν` (maximal-matching
argument) and the well-known energy–matching bound `E(G) ≥ 2ν(G)` (Gutman-era).
Together they prove it.

## Disposition in MatyOS

Promoted from `candidate` to `known` in `known.py` once the second link
(`E ≥ 2ν`) was confirmed. This is the honest loop working: MatyOS surfaced a bound
it could not account for, flagged it truthfully, and it was closed only after the
missing theorem was verified — never claimed before that. The sibling lead
`docs/conjectures/radius-le-total-domination.md` remains genuinely open.
