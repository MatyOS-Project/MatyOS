"""Graphs — a discovery domain beyond numbers (the Graffiti move).

Instead of a formula for a sequence, the interesting objects here are *relations
between graph invariants* — e.g. "the average degree is at most the maximum
degree", or a tighter, less obvious bound. Fajtlowicz's Graffiti made real
conjectures this way: compute invariants over many graphs and surface the
inequalities that hold on all of them (and are tight on some).

Pure Python, no dependencies; built for small graphs. Invariants are the cheap
combinatorial ones (order, size, degrees, triangles, distances). Spectral
invariants would need linear algebra and are left for later.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from fractions import Fraction
from itertools import combinations

from matyos.discovery.objects import MathObject


@dataclass(frozen=True)
class Graph(MathObject):
    """A simple undirected graph: ``n`` vertices 0..n-1 and a set of edges."""

    n: int = 0
    edges: frozenset = field(default_factory=frozenset)
    name: str = ""
    domain: str = field(default="graph", init=False)

    @staticmethod
    def of(n: int, edge_list, name: str = "") -> "Graph":
        e = frozenset(frozenset((a, b)) for a, b in edge_list if a != b)
        return Graph(n=n, edges=e, name=name)

    def _adj(self) -> dict[int, set]:
        adj = {v: set() for v in range(self.n)}
        for e in self.edges:
            a, b = tuple(e)
            adj[a].add(b)
            adj[b].add(a)
        return adj

    def key(self) -> str:
        return f"graph:n={self.n}:" + ",".join(sorted("-".join(map(str, sorted(e))) for e in self.edges))


# ---- invariants: each maps a Graph to a number (int or Fraction) -------------

def order(g: Graph) -> int:
    return g.n


def size(g: Graph) -> int:
    return len(g.edges)


def _degrees(g: Graph) -> list[int]:
    adj = g._adj()
    return [len(adj[v]) for v in range(g.n)]


def max_degree(g: Graph) -> int:
    d = _degrees(g)
    return max(d) if d else 0


def min_degree(g: Graph) -> int:
    d = _degrees(g)
    return min(d) if d else 0


def avg_degree(g: Graph) -> Fraction:
    return Fraction(2 * size(g), g.n) if g.n else Fraction(0)


def triangles(g: Graph) -> int:
    adj = g._adj()
    t = 0
    for a, b, c in combinations(range(g.n), 3):
        if b in adj[a] and c in adj[a] and c in adj[b]:
            t += 1
    return t


def _bfs_dist(adj, s, n):
    dist = {s: 0}
    q = deque([s])
    while q:
        u = q.popleft()
        for w in adj[u]:
            if w not in dist:
                dist[w] = dist[u] + 1
                q.append(w)
    return dist


def is_connected(g: Graph) -> bool:
    if g.n <= 1:
        return True
    return len(_bfs_dist(g._adj(), 0, g.n)) == g.n


def diameter(g: Graph) -> int:
    """Longest shortest-path (only meaningful for connected graphs; else 0)."""
    if not is_connected(g):
        return 0
    adj = g._adj()
    return max(max(_bfs_dist(adj, s, g.n).values()) for s in range(g.n))


def radius(g: Graph) -> int:
    if not is_connected(g):
        return 0
    adj = g._adj()
    return min(max(_bfs_dist(adj, s, g.n).values()) for s in range(g.n))


def independence_number(g: Graph) -> int:
    """Largest set of vertices with no edge between them (brute force; small n)."""
    adj = g._adj()
    best = 0
    for mask in range(1 << g.n):
        sel = [v for v in range(g.n) if mask >> v & 1]
        if len(sel) > best and all(b not in adj[a] for a, b in combinations(sel, 2)):
            best = len(sel)
    return best


def clique_number(g: Graph) -> int:
    """Largest set of mutually adjacent vertices (brute force; small n)."""
    adj = g._adj()
    best = 0
    for mask in range(1 << g.n):
        sel = [v for v in range(g.n) if mask >> v & 1]
        if len(sel) > best and all(b in adj[a] for a, b in combinations(sel, 2)):
            best = len(sel)
    return best


def chromatic_number(g: Graph) -> int:
    """Fewest colors for a proper coloring (backtracking; small n)."""
    if g.n == 0:
        return 0
    adj = g._adj()
    for k in range(1, g.n + 1):
        color = [0] * g.n

        def bt(v):
            if v == g.n:
                return True
            for c in range(1, k + 1):
                if all(color[w] != c for w in adj[v]):
                    color[v] = c
                    if bt(v + 1):
                        return True
                    color[v] = 0
            return False

        if bt(0):
            return k
    return g.n


def vertex_cover_number(g: Graph) -> int:
    """Smallest set of vertices covering every edge (= n - independence number)."""
    return g.n - independence_number(g)


INVARIANTS = {
    "order": order, "size": size, "max_degree": max_degree,
    "min_degree": min_degree, "avg_degree": avg_degree,
    "triangles": triangles, "diameter": diameter, "radius": radius,
    "independence_number": independence_number, "clique_number": clique_number,
    "chromatic_number": chromatic_number, "vertex_cover_number": vertex_cover_number,
}


# ---- spectral invariants (need mpmath for eigenvalues) -----------------------

try:
    import mpmath as _mp
    HAVE_SPECTRAL = True
except Exception:                       # pragma: no cover
    HAVE_SPECTRAL = False


def _adjacency_eigs(g: Graph):
    adj = g._adj()
    A = _mp.matrix(g.n, g.n)
    for v in range(g.n):
        for w in adj[v]:
            A[v, w] = 1
    return sorted(_mp.eigsy(A, eigvals_only=True))     # ascending, real


def _laplacian_eigs(g: Graph):
    adj = g._adj()
    L = _mp.matrix(g.n, g.n)
    for v in range(g.n):
        L[v, v] = len(adj[v])
        for w in adj[v]:
            L[v, w] = -1
    return sorted(_mp.eigsy(L, eigvals_only=True))


def spectral_radius(g: Graph) -> float:
    """Largest adjacency eigenvalue. Satisfies avg_degree <= it <= max_degree."""
    return float(_adjacency_eigs(g)[-1]) if g.n else 0.0


def energy(g: Graph) -> float:
    """Graph energy: sum of absolute values of adjacency eigenvalues."""
    return float(sum(abs(e) for e in _adjacency_eigs(g))) if g.n else 0.0


def algebraic_connectivity(g: Graph) -> float:
    """Fiedler value: 2nd-smallest Laplacian eigenvalue (0 iff disconnected).
    Bounded above by vertex connectivity and by min_degree."""
    if g.n < 2:
        return 0.0
    return float(_laplacian_eigs(g)[1])


def laplacian_spectral_radius(g: Graph) -> float:
    """Largest Laplacian eigenvalue. Satisfies it <= order and >= max_degree+1."""
    return float(_laplacian_eigs(g)[-1]) if g.n else 0.0


SPECTRAL_INVARIANTS = {
    "spectral_radius": spectral_radius, "energy": energy,
    "algebraic_connectivity": algebraic_connectivity,
    "laplacian_spectral_radius": laplacian_spectral_radius,
} if HAVE_SPECTRAL else {}


def all_invariants() -> dict:
    """Combinatorial invariants, plus spectral ones when mpmath is available."""
    return {**INVARIANTS, **SPECTRAL_INVARIANTS}


# ---- graph generators --------------------------------------------------------

def path(n):    return Graph.of(n, [(i, i + 1) for i in range(n - 1)], f"P{n}")
def cycle(n):   return Graph.of(n, [(i, (i + 1) % n) for i in range(n)], f"C{n}")
def complete(n):return Graph.of(n, list(combinations(range(n), 2)), f"K{n}")
def star(n):    return Graph.of(n, [(0, i) for i in range(1, n)], f"star{n}")
def wheel(n):   # hub 0 + cycle on 1..n-1
    return Graph.of(n, [(0, i) for i in range(1, n)] +
                    [(i, i + 1) for i in range(1, n - 1)] + [(n - 1, 1)], f"W{n}")
def complete_bipartite(a, b):
    return Graph.of(a + b, [(i, a + j) for i in range(a) for j in range(b)], f"K{a},{b}")


def sample_graphs() -> list[Graph]:
    """A diverse spread of small connected graphs to conjecture over."""
    gs = []
    for n in range(3, 8):
        gs += [path(n), cycle(n), complete(n), star(n)]
        if n >= 4:
            gs.append(wheel(n))
    for a in range(1, 4):
        for b in range(a, 4):
            gs.append(complete_bipartite(a, b))
    return [g for g in gs if is_connected(g)]


# ---- the Graffiti move: conjecture inequalities between invariants -----------

@dataclass(frozen=True)
class GraphConjecture:
    text: str            # e.g. "avg_degree <= max_degree"
    support: int         # graphs it held on
    tight: int           # graphs where equality held


def graffiti_search(graphs=None, invariants=None) -> list[GraphConjecture]:
    """Find invariant inequalities A(G) <= B(G) holding on every sampled graph.

    Keeps only *tight* inequalities (equality on at least one graph) that are not
    identities (strict on at least one) — those are the interesting conjectures.
    They hold on the sample; proving them for all graphs is a human/Lean job.
    """
    graphs = graphs or sample_graphs()
    inv = invariants or all_invariants()
    names = list(inv)
    eps = 1e-9                          # tolerance: spectral invariants are floats
    out: list[GraphConjecture] = []
    vals = {name: [float(inv[name](g)) for g in graphs] for name in names}
    for a in names:
        for b in names:
            if a == b:
                continue
            va, vb = vals[a], vals[b]
            if all(x <= y + eps for x, y in zip(va, vb)):
                tight = sum(1 for x, y in zip(va, vb) if abs(x - y) <= eps)
                strict = sum(1 for x, y in zip(va, vb) if y - x > eps)
                if tight >= 1 and strict >= 1:      # tight, but a real inequality
                    out.append(GraphConjecture(f"{a} <= {b}", len(graphs), tight))
    out.sort(key=lambda c: c.tight, reverse=True)
    return out


def classified_search(graphs=None, invariants=None) -> list[dict]:
    """Graffiti search + the novelty filter: each inequality tagged known /
    derived / candidate (see ``matyos.discovery.known``).

    Returns dicts sorted so the ``candidate`` bounds — the only ones MatyOS's
    knowledge cannot explain — come first; those are what a human should look at.
    """
    from matyos.discovery import known
    rank = {"candidate": 0, "derived": 1, "known": 2}
    out = []
    for c in graffiti_search(graphs, invariants):
        cls = known.classify(c.text)
        out.append({"statement": c.text, "held_on": c.support, "tight_on": c.tight,
                    "novelty": cls["status"], "reason": cls["reason"]})
    out.sort(key=lambda d: (rank[d["novelty"]], -d["tight_on"]))
    return out
