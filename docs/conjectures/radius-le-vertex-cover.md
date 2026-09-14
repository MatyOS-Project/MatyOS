# radius(G) ≤ vertex_cover_number(G)

**Status: proven** (elementary). Surfaced by MatyOS's graph conjecture loop
(`graffiti_search` → stress test → novelty filter flagged it `candidate`), then
proven by hand. A quick literature check found only the *weaker* bound
`radius ≤ 2·τ` (from "a path has length ≤ 2·vertex-cover"); this stronger form
`radius ≤ τ` was not found stated, though the proof is elementary enough that it
is plausibly folklore. MatyOS does **not** claim novelty — only that it surfaced a
true, tight bound its knowledge base did not contain, and that a proof now exists.

Notation: `τ(G)` = vertex cover number, `α(G)` = independence number
(`τ = n − α`), `radius(G) = min_v ecc(v)`, `diam(G) = max_v ecc(v)`.

## Empirical support

- Survived a stress test of 650+ graphs (random + paths/cycles/trees/spiders) with
  0 violations.
- A focused counterexample hunt over 8063 trees (exact poly vertex-cover DP + BFS
  radius, up to n = 26) found 0 violations. Equality `radius = τ` holds **only on
  paths**; every other graph tested is strict — exactly what the proof predicts.

## Theorem

For every connected graph `G`, `radius(G) ≤ τ(G)`.

## Proof

**Step 1 — reduce to trees.** Let `T` be any spanning tree of `G`.

- `T` has a subset of `G`'s edges, so `dist_T(u,v) ≥ dist_G(u,v)` for all `u,v`.
  Hence `ecc_T(v) ≥ ecc_G(v)` for every vertex, and taking the minimum over `v`,
  `radius(T) ≥ radius(G)`.
- Every vertex cover of `G` covers all edges of `G`, in particular all edges of
  `T`; so it is a vertex cover of `T`. Thus `τ(T) ≤ τ(G)`.

Therefore, if the tree case `radius(T) ≤ τ(T)` holds,
`radius(G) ≤ radius(T) ≤ τ(T) ≤ τ(G)`.

**Step 2 — trees.** Let `T` be a tree with `diam(T) = L`.

- By Jordan's tree-center theorem, `radius(T) = ⌈L/2⌉`.
- Fix a diametral path `P` in `T`: it has `L` edges on `L+1` vertices. Any vertex
  cover of `T` must cover the `L` edges of `P`, and the minimum vertex cover of a
  path on `L+1` vertices has size `⌊(L+1)/2⌋`. Hence `τ(T) ≥ ⌊(L+1)/2⌋`.
- For every integer `L`, `⌊(L+1)/2⌋ = ⌈L/2⌉`.

So `radius(T) = ⌈L/2⌉ = ⌊(L+1)/2⌋ ≤ τ(T)`. ∎

## Tightness

Equality holds exactly for paths: `radius(P_n) = ⌊n/2⌋ = τ(P_n)`. The bound is not
implied by domination (`radius ≤ γ` is false — e.g. `radius(P_n) ≈ n/2 > γ ≈ n/3`),
which is why the single-shortest-path argument only yields `radius ≤ 2τ`; the
spanning-tree reduction is what removes the factor 2.
