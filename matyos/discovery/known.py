"""A novelty filter for graph-invariant inequalities.

Graffiti surfaces tight inequalities ``A(G) <= B(G)`` that hold on a sample. Most
are already theorems, or follow from theorems. To be an honest *conjecture*
engine we must separate the three cases:

- ``known``     — the inequality is an established theorem (or a trivial bound),
                  listed in ``KNOWN`` with its justification.
- ``derived``   — not listed directly, but *implied* by the known bounds through
                  a chain (transitive closure): if ``A <= X`` and ``X <= B`` are
                  both known then ``A <= B`` is not new. The chain is reported.
- ``candidate`` — neither. It held on the sample and is not implied by anything
                  we know. That does **not** mean it is new — only that MatyOS
                  cannot rule it out, so a human/literature check is needed.

This is deliberately conservative: a bound is called ``candidate`` only when our
curated knowledge cannot explain it. The DB is small and hand-checked; growing it
strictly improves the filter (more bounds become ``known``/``derived``). It is the
piece Fajtlowicz's Graffiti and later conjecture engines all needed — MatyOS never
claims novelty, it reports what its knowledge cannot account for.
"""

from __future__ import annotations

# Each entry: (a, b, reason) asserting a(G) <= b(G) for all connected graphs.
# Only established theorems or trivial-by-definition bounds belong here; every
# one carries a one-line justification so the DB stays auditable.
KNOWN: list[tuple[str, str, str]] = [
    # degree chain (handshake + max/min)
    ("min_degree", "avg_degree", "handshake: average is between min and max"),
    ("avg_degree", "max_degree", "average degree <= maximum degree"),
    # spectral bracket (classic): avg_degree <= spectral_radius <= max_degree
    ("avg_degree", "spectral_radius", "avg degree <= largest adjacency eigenvalue"),
    ("spectral_radius", "max_degree", "largest adjacency eigenvalue <= max degree"),
    # energy dominates the spectral radius (energy = sum|lambda| >= |lambda_max|)
    ("spectral_radius", "energy", "energy = sum|eigenvalue| >= largest eigenvalue"),
    # colouring
    ("clique_number", "chromatic_number", "omega <= chi (a clique needs its own colours)"),
    ("clique_number", "laplacian_spectral_radius", "omega <= Delta+1 <= largest Laplacian eig"),
    ("chromatic_number", "laplacian_spectral_radius", "chi <= largest Laplacian eigenvalue (known)"),
    # distances
    ("radius", "diameter", "radius <= diameter by definition"),
    # Laplacian / algebraic connectivity (Fiedler)
    ("algebraic_connectivity", "min_degree", "Fiedler: a(G) <= vertex connectivity <= min degree"),
    ("algebraic_connectivity", "laplacian_spectral_radius", "smallest nonzero <= largest Laplacian eig"),
    ("laplacian_spectral_radius", "order", "largest Laplacian eigenvalue <= number of vertices"),
    # independence / cover (Gallai): vertex_cover = order - independence
    ("min_degree", "vertex_cover_number", "delta <= tau: a max-independent vertex's neighbours lie in the cover"),
    # radius vs independence: an old Graffiti theorem (Fajtlowicz-Waller;
    # Favaron-Maheo-Sacle): radius(G) <= independence number for connected graphs.
    ("radius", "independence_number", "radius <= alpha (a proven Graffiti theorem)"),
    # radius vs vertex cover: proven via spanning-tree reduction + Jordan's tree
    # centre theorem (radius(T)=ceil(diam/2) <= floor((diam+1)/2) <= tau(T)).
    # See docs/conjectures/radius-le-vertex-cover.md. Stronger than the folklore
    # radius <= 2*tau; surfaced by MatyOS's loop, then proven.
    ("radius", "vertex_cover_number", "radius <= tau (proven; spanning-tree reduction to trees)"),
    # matching vs cover: every matching edge needs its own distinct cover vertex
    ("matching_number", "vertex_cover_number", "nu <= tau: each matching edge needs its own cover vertex"),
    # Whitney's inequality: vertex-connectivity <= edge-connectivity <= min degree
    ("vertex_connectivity", "edge_connectivity", "Whitney: kappa <= lambda"),
    ("edge_connectivity", "min_degree", "Whitney: lambda <= delta"),
    # domination vs independence: a maximal independent set is dominating
    ("domination_number", "independence_number", "gamma <= alpha: a maximal independent set dominates"),
    # degeneracy is at most the maximum degree
    ("degeneracy", "max_degree", "degeneracy <= Delta (min-degree peeling)"),
    # --- proven by MatyOS's loop this session (surfaced -> stress-tested -> proven) ---
    # radius <= matching: radius(G) <= radius(T) <= tau(T) = nu(T) (Koenig, T a tree)
    # <= nu(G). Stronger than radius <= tau.
    ("radius", "matching_number", "radius <= nu (proven; via radius<=tau on a spanning tree + Koenig)"),
    # degeneracy <= tau: every subgraph H has a vertex of degree <= tau (an
    # independent-set vertex, whose neighbours all lie in the cover; or |H|<=tau).
    ("degeneracy", "vertex_cover_number", "degeneracy <= tau (every subgraph has a low-degree vertex in the cover)"),
    # domination <= tau: a vertex cover is a dominating set (isolate-free graphs).
    ("domination_number", "vertex_cover_number", "gamma <= tau: a vertex cover dominates an isolate-free graph"),
    # degeneracy <= spectral radius: some subgraph H has min-degree = degeneracy, and
    # lambda_max(G) >= lambda_max(H) >= avg_degree(H) >= min_degree(H) = degeneracy.
    ("degeneracy", "spectral_radius", "degeneracy <= lambda_max (subgraph with that min-degree; eigenvalue interlacing)"),
    # min_degree <= degeneracy: G itself is a subgraph with min-degree delta, so
    # the max-over-subgraphs min-degree is at least delta. Chains with Whitney to
    # derive vertex_connectivity <= degeneracy and edge_connectivity <= degeneracy.
    ("min_degree", "degeneracy", "delta <= degeneracy (G is a subgraph of min-degree delta)"),
    # domination <= matching: a known theorem for graphs without isolated vertices.
    ("domination_number", "matching_number", "gamma <= nu (known theorem, isolate-free graphs)"),
    # chromatic <= energy: Wilf gives chi <= 1 + lambda_max; eigenvalues sum to 0 so
    # energy = 2*(sum of positive eigenvalues) >= 2*lambda_max, hence chi <= 1 + E/2
    # <= E for any graph with an edge (E >= 2).
    ("chromatic_number", "energy", "chi <= 1+lambda_max (Wilf) <= 1+E/2 <= E (graphs with an edge)"),
    # eccentricity / distance ordering
    ("radius", "average_eccentricity", "min eccentricity <= mean eccentricity"),
    ("average_eccentricity", "diameter", "mean eccentricity <= max eccentricity"),
    ("average_distance", "diameter", "mean distance <= maximum distance"),
    # total domination dominates ordinary domination
    ("domination_number", "total_domination_number", "gamma <= gamma_t (a total dominating set dominates)"),
    # matching vs edge cover: nu <= rho since 2*nu <= n = nu + rho (Gallai)
    ("matching_number", "edge_cover_number", "nu <= rho: 2*nu <= n = nu + rho (Gallai)"),
    # independence vs edge cover: alpha <= rho = n - nu  <=>  nu <= tau (Gallai/Koenig)
    ("independence_number", "edge_cover_number", "alpha <= rho (equivalently nu <= tau)"),
    # trivial: an edge cover is a set of edges; a (total) dominating set of vertices
    ("edge_cover_number", "size", "an edge cover is a set of edges"),
    ("total_domination_number", "order", "a total dominating set is a set of vertices"),
    # mean distance from a vertex is at most its eccentricity, so on average:
    ("average_distance", "average_eccentricity", "mean distance <= mean eccentricity (per-vertex)"),
    # Chung (1988): average distance <= independence number
    ("average_distance", "independence_number", "Chung 1988: mean distance <= alpha"),
    # total domination <= energy: gamma_t <= 2*nu (a maximum matching's vertices
    # totally dominate) and E(G) >= 2*nu (well-known energy-matching bound), so
    # gamma_t <= 2*nu <= E. Both links are established theorems. The factor-2 keeps
    # it off the invariant-name chain, so it is listed directly.
    ("total_domination_number", "energy", "gamma_t <= 2*nu <= E (both known: gamma_t<=2nu and E>=2nu)"),
    # clique vs energy: E(G) = sum|lambda| >= lambda_max + |lambda_min|
    # >= (omega-1) + 1 = omega (a K_omega subgraph forces lambda_max >= omega-1).
    ("clique_number", "energy", "omega <= lambda_max + |lambda_min| <= energy"),
    # trivial upper bounds by order (n) — true by definition for connected graphs
    ("clique_number", "order", "a clique is a set of vertices"),
    ("chromatic_number", "order", "at most n colours"),
    ("independence_number", "order", "an independent set is a set of vertices"),
    ("vertex_cover_number", "order", "a cover is a set of vertices"),
    ("diameter", "order", "a shortest path has < n vertices"),
    ("radius", "order", "radius <= diameter < n"),
    ("max_degree", "order", "a vertex has < n neighbours"),
    ("spectral_radius", "order", "largest adjacency eigenvalue <= n-1"),
    ("algebraic_connectivity", "order", "a(G) <= n"),
    # trivial upper bounds by size (m); connected => m >= n-1
    ("max_degree", "size", "a vertex's edges are among the m edges"),
    ("diameter", "size", "a shortest path uses <= m edges"),
    ("radius", "size", "radius <= diameter <= m"),
    ("independence_number", "size", "alpha <= n-1 <= m for connected graphs"),
    ("vertex_cover_number", "size", "tau <= n-1 <= m for connected graphs"),
    ("spectral_radius", "size", "largest adjacency eigenvalue <= m for connected graphs"),
]

_KNOWN_PAIRS = {(a, b) for a, b, _ in KNOWN}
_REASON = {(a, b): r for a, b, r in KNOWN}
_SUCC: dict[str, set] = {}
for _a, _b, _ in KNOWN:
    _SUCC.setdefault(_a, set()).add(_b)


def _chain(a: str, b: str) -> list[str] | None:
    """A path a -> ... -> b through known <= edges (length >= 2), or None.

    Found by breadth-first search over the known-inequality graph. A returned
    path means ``a <= b`` is implied by transitivity, so the bound is not new.
    """
    from collections import deque
    q = deque([[a]])
    seen = {a}
    while q:
        path = q.popleft()
        for nxt in _SUCC.get(path[-1], ()):
            if nxt == b and len(path) >= 2:          # >=2 edges => a real chain
                return path + [nxt]
            if nxt not in seen:
                seen.add(nxt)
                q.append(path + [nxt])
    return None


def classify(text: str) -> dict:
    """Classify an inequality string ``"a <= b"`` as known / derived / candidate.

    Returns {"status", "reason"} and, for ``derived``, the implying ``chain``.
    An unparseable string is returned as ``candidate`` with a note, never raised.
    """
    if " <= " not in text:
        return {"status": "candidate", "reason": f"unparseable: {text!r}"}
    a, b = text.split(" <= ", 1)
    if (a, b) in _KNOWN_PAIRS:
        return {"status": "known", "reason": _REASON[(a, b)]}
    chain = _chain(a, b)
    if chain is not None:
        return {"status": "derived",
                "reason": "implied by known bounds: " + " <= ".join(chain),
                "chain": chain}
    return {"status": "candidate",
            "reason": "not implied by MatyOS's known-inequality DB; verify against "
                      "the literature before treating as new"}
