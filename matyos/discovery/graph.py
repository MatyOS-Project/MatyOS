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


INVARIANTS = {
    "order": order, "size": size, "max_degree": max_degree,
    "min_degree": min_degree, "avg_degree": avg_degree,
    "triangles": triangles, "diameter": diameter, "radius": radius,
}


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
    inv = invariants or INVARIANTS
    names = list(inv)
    out: list[GraphConjecture] = []
    vals = {name: [Fraction(inv[name](g)) for g in graphs] for name in names}
    for a in names:
        for b in names:
            if a == b:
                continue
            va, vb = vals[a], vals[b]
            if all(x <= y for x, y in zip(va, vb)):
                tight = sum(1 for x, y in zip(va, vb) if x == y)
                strict = sum(1 for x, y in zip(va, vb) if x < y)
                if tight >= 1 and strict >= 1:      # tight, but a real inequality
                    out.append(GraphConjecture(f"{a} <= {b}", len(graphs), tight))
    out.sort(key=lambda c: c.tight, reverse=True)
    return out
