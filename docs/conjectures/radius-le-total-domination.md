# radius(G) ≤ total_domination_number(G) — OPEN (to us)

**Status: candidate / unresolved.** Surfaced by MatyOS's widened graph loop and it
is the *only* bound the current knowledge base cannot explain. It is **not** proven
here and **not** confirmed as a published theorem — it is an honest open lead.

Notation: `γ_t(G)` = total domination number (smallest `S` such that every vertex,
including those of `S`, has a neighbour in `S`); `radius(G) = min_v ecc(v)`.

## Evidence

- 0 violations across 1000+ graphs: the general stress battery (random +
  paths/cycles/stars/Petersen/grids), a targeted hunt over spiders, caterpillars
  and trees up to n = 15, and an exact-`γ_t` check on larger trees up to n = 20.
- The ratio `radius / γ_t` never exceeds 1.0, and **equality holds only on paths
  `P_{4m}`** (spiders and all other families tested sit strictly below). The path
  is the unique extremal family — so if the bound holds, factor-1 is tight and is
  the true constant (not merely the 1.5 proved below).

## Direct factor-1 proof: attempted, not found

A direct proof of `radius ≤ γ_t` was attempted and **not obtained**. Every approach
loses a constant factor: the geodesic-covering count (each `S`-vertex is adjacent
to ≤ 3 consecutive vertices of a shortest path) gives only `≤ 3γ_t−1`, and that
factor-3 count is tight for general graphs; the spanning-tree reduction that proved
`radius ≤ vertex_cover` fails because `γ_t`'s monotonicity runs the wrong way under
edge deletion. The best established constant is 1.5 (below). Closing 1.5 → 1
appears to need an argument specific to the minimum eccentricity (the centre) that
we do not have.

## What is proven / known (partial — factor > 1)

**`radius(G) ≤ 1.5·γ_t(G)`.** DeLaViña, Pepper and Waller proved `γ(G) ≥ ⅔·radius(G)`
for the (ordinary) domination number, i.e. `radius ≤ 1.5·γ`. Since `γ ≤ γ_t`, we get
`radius ≤ 1.5·γ_t`. This is the best factor established.

**`radius(G) ≤ 3·γ_t(G) − 1`** (self-contained, weaker). Let `c` be a centre,
`r = radius`, and take a shortest (induced) path `c = v_0, …, v_r`. On an induced
path any vertex is adjacent to at most three *consecutive* path vertices (a
neighbour of `v_i, v_j` with `|i−j| ≥ 3` shortcuts the path), so a total dominating
set needs `≥ (r+1)/3` vertices: `radius ≤ 3γ_t − 1`. ∎

The **factor-1** bound `radius ≤ γ_t` (tight on paths) is what MatyOS surfaced and
is **not** proven here — only `radius ≤ 1.5·γ_t`.

## Why the factor-1 bound resisted

The `radius ≤ vertex_cover` proof reduced to trees via a spanning tree, using
`τ(T) ≤ τ(G)`. That fails for total domination: a total dominating set of a
spanning tree `T` is still one for `G`, so `γ_t(G) ≤ γ_t(T)` — the **wrong
direction** for the reduction. So `radius ≤ γ_t` is not a corollary of the tree
case, and the induced-path count only gives factor 3.

## Literature (citation search — inconclusive)

Actively checked and **could not confirm** the exact clean inequality `radius ≤ γ_t`
as a stated theorem. Sources checked: the DeLaViña–Pepper "Some conjectures of
Graffiti.pc on total domination" list, the Graffiti.pc conjecture list (its total-
domination entry, #247, is `γ_t ≥ 2·path-cover` — a different bound), Henning–Yeo's
2014 DAM paper "A new lower bound for the total domination number… proving a
Graffiti.pc Conjecture" (#233, phrased via eccentricity of a specific vertex set /
triameter), and arXiv:1409.4116. All give *neighbouring* results — notably the
proven `γ ≥ ⅔·radius` used above — but not `radius ≤ γ_t` verbatim.

So the honest status is: **very likely known or a short consequence in the
Graffiti.pc total-domination literature, but not confirmed by a citation here, and
the factor-1 form not proven by us.** A deeper literature dive (or a direct proof)
is the honest next step. MatyOS neither proves it nor claims a citation.

## Disposition in MatyOS

Left tagged `candidate` by the novelty filter (not promoted to `known`). This is
the engine behaving correctly: it surfaced a true-on-every-test bound its knowledge
cannot account for, and MatyOS declines to claim more than it can back up.
