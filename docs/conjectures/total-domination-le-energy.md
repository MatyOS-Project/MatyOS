# total_domination_number(G) ≤ energy(G) — OPEN (to us)

**Status: candidate / unresolved.** Surfaced by MatyOS's widened graph loop (with
spectral invariants enabled). It is **not** proven here and **not** confirmed as a
published theorem — an honest open lead, kept tagged `candidate`, never claimed.

Notation: `γ_t(G)` = total domination number (smallest `S` such that every vertex,
`S` included, has a neighbour in `S`); `ν(G)` = matching number; `E(G)` = graph
energy = sum of the absolute values of the adjacency eigenvalues.

## Evidence

- 0 violations across 443 graphs (random + paths/cycles/stars/Petersen/grids/cube).

## A plausible derivation — but with one unverified link

There is a candidate proof by transitivity:

1. **`γ_t(G) ≤ 2·ν(G)`** — *known*: the vertex set of any maximal matching is a
   total dominating set (a standard result), so `γ_t ≤ 2ν`. Held on 426/426 test
   graphs here, consistent with the theorem.
2. **`E(G) ≥ 2·ν(G)`** — held on 426/426 test graphs here, **but NOT verified by us
   as a stated theorem or proved.** This is the missing link.

If (2) is a theorem, then `γ_t ≤ 2ν ≤ E`, done. Because (2) is unconfirmed, the
chain is a **lead, not a proof**, and this bound stays a candidate.

## Literature

The energy/domination literature is active but, on a search, addresses *different*
quantities: minimum *dominating energy* `E_D(G)`, adjacency-rank bounds
(`γ_t ≤ n − m_G(0)`, Abiad et al. 2023), and positive/negative square energies. The
clean inequality `γ_t ≤ E` was **not** located as a stated theorem; it is plausibly
known or a short consequence (e.g. via the chain above) in that literature.

## Disposition in MatyOS

Left tagged `candidate` by the novelty filter — not promoted to `known`. MatyOS
surfaced a bound true on every test it cannot account for, and declines to claim
more than it can back up. **Next honest step is a human/literature check**, in
particular whether `E(G) ≥ 2ν(G)` is an established theorem (which would settle
this immediately). See the sibling lead in
`docs/conjectures/radius-le-total-domination.md`.
