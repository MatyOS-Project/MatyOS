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
