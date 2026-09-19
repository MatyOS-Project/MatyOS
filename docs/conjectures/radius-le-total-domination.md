# radius(G) ≤ total_domination_number(G) — OPEN (to us)

**Status: candidate / unresolved.** Surfaced by MatyOS's widened graph loop and it
is the *only* bound the current knowledge base cannot explain. It is **not** proven
here and **not** confirmed as a published theorem — it is an honest open lead.

Notation: `γ_t(G)` = total domination number (smallest `S` such that every vertex,
including those of `S`, has a neighbour in `S`); `radius(G) = min_v ecc(v)`.

## Evidence

- 0 violations across 900+ graphs: the general stress battery (random +
  paths/cycles/stars/Petersen/grids) and a targeted hunt over spiders,
  caterpillars and trees up to n = 15 built specifically to make `radius` large
  and `γ_t` small.
- Equality `radius = γ_t` is attained on paths (e.g. `P_4`, `P_8`), so if true the
  bound is tight.

## What is proven here

**`radius(G) ≤ 3·γ_t(G) − 1`.** Let `c` be a centre, `r = ecc(c) = radius`, and
take a shortest (hence induced) path `c = v_0, v_1, …, v_r`. On an induced path any
single vertex is adjacent to at most three *consecutive* path vertices (a neighbour
of `v_i` and `v_j` with `|i−j| ≥ 3` would be a shortcut, contradicting
shortest-path). A total dominating set must supply each of the `r+1` path vertices
with a neighbour in `S`, so `γ_t ≥ (r+1)/3`, i.e. `radius ≤ 3γ_t − 1`. ∎

## Why the factor-1 bound resisted

The `radius ≤ vertex_cover` proof reduced to trees via a spanning tree, using
`τ(T) ≤ τ(G)`. That fails for total domination: a total dominating set of a
spanning tree `T` is still one for `G`, so `γ_t(G) ≤ γ_t(T)` — the **wrong
direction** for the reduction. So `radius ≤ γ_t` is not a corollary of the tree
case, and the induced-path count only gives factor 3.

## Literature

Closely related results exist and are almost certainly the right neighbourhood:
DeLaViña et al.'s Graffiti.pc conjectures give lower bounds on `γ_t` in terms of
eccentricity/radius (e.g. `γ_t(G) ≥ ⅔(ecc_G(B)+1)` for a specific set `B`), and
`γ(G) ≥ ⅔·radius` is known. The exact clean inequality `radius ≤ γ_t` was **not**
located as a stated theorem in a quick search; it is plausibly known or a short
consequence in that literature. **A human/literature check is the honest next
step** — MatyOS neither proved it nor found a citation, and does not claim it.

## Disposition in MatyOS

Left tagged `candidate` by the novelty filter (not promoted to `known`). This is
the engine behaving correctly: it surfaced a true-on-every-test bound its knowledge
cannot account for, and MatyOS declines to claim more than it can back up.
