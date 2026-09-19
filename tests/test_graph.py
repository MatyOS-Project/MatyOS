"""Tests for the graph discovery domain (invariants + the Graffiti move).

Pure Python, no mpmath — these run fast.
"""

from matyos.discovery import graph as G


def test_invariants_on_known_graphs():
    c5 = G.cycle(5)
    assert G.order(c5) == 5 and G.size(c5) == 5
    assert G.avg_degree(c5) == 2 and G.diameter(c5) == 2 and G.radius(c5) == 2
    assert G.triangles(c5) == 0
    k4 = G.complete(4)
    assert G.triangles(k4) == 4 and G.diameter(k4) == 1 and G.max_degree(k4) == 3


def test_handshake_sum_of_degrees_is_twice_size():
    g = G.wheel(6)
    assert G.avg_degree(g) * G.order(g) == 2 * G.size(g)


def test_connectivity():
    assert G.is_connected(G.path(5))
    disc = G.Graph.of(4, [(0, 1)])          # two isolated + an edge
    assert not G.is_connected(disc)


def test_graffiti_rediscovers_true_inequalities():
    conj = {c.text for c in G.graffiti_search()}
    # genuine theorems for connected graphs, surfaced from the sample
    assert "radius <= diameter" in conj
    assert "min_degree <= max_degree" in conj
    assert "avg_degree <= max_degree" in conj


def test_graffiti_conjectures_are_tight_and_nontrivial():
    for c in G.graffiti_search():
        assert 1 <= c.tight < c.support        # tight on some, strict on some


def test_chromatic_independence_clique_values():
    k4 = G.complete(4)
    assert G.chromatic_number(k4) == 4 and G.clique_number(k4) == 4 and G.independence_number(k4) == 1
    c5 = G.cycle(5)
    assert G.chromatic_number(c5) == 3 and G.clique_number(c5) == 2 and G.independence_number(c5) == 2
    assert G.chromatic_number(G.cycle(4)) == 2       # even cycle is 2-colorable
    assert G.vertex_cover_number(c5) == 5 - G.independence_number(c5)


def test_graffiti_rediscovers_clique_le_chromatic():
    conj = {c.text for c in G.graffiti_search()}
    assert "clique_number <= chromatic_number" in conj   # omega <= chi, a theorem


def test_novelty_filter_classifies_known_derived_candidate():
    from matyos.discovery import known
    # a listed theorem is 'known'
    assert known.classify("clique_number <= chromatic_number")["status"] == "known"
    # implied by a chain is 'derived', with a chain from the lhs to the rhs
    d = known.classify("min_degree <= max_degree")
    assert d["status"] == "derived"
    assert d["chain"][0] == "min_degree" and d["chain"][-1] == "max_degree"
    # a proven Graffiti theorem we added to the DB is 'known'
    assert known.classify("radius <= independence_number")["status"] == "known"
    # not implied by the DB is 'candidate' (honest: not a novelty claim)
    assert known.classify("triangles <= girth")["status"] == "candidate"


def test_new_invariant_values():
    # values checked by hand for the six invariants added when widening the engine
    assert G.domination_number(G.cycle(5)) == 2 and G.domination_number(G.complete(4)) == 1
    assert G.matching_number(G.complete(4)) == 2 and G.matching_number(G.path(4)) == 2
    assert G.vertex_connectivity(G.complete(4)) == 3 and G.vertex_connectivity(G.path(5)) == 1
    assert G.edge_connectivity(G.cycle(5)) == 2 and G.edge_connectivity(G.path(5)) == 1
    assert G.degeneracy(G.complete(4)) == 3 and G.degeneracy(G.cycle(5)) == 2
    assert G.girth(G.cycle(5)) == 5 and G.girth(G.complete(4)) == 3
    assert G.girth(G.path(5)) == G.order(G.path(5)) + 1     # acyclic sentinel
    # Petersen graph: a good all-round check
    p = G.petersen()
    assert G.vertex_connectivity(p) == 3 and G.girth(p) == 5 and G.edge_connectivity(p) == 3


def test_new_known_bounds_classified():
    from matyos.discovery import known
    # Whitney chain: vertex_connectivity <= edge_connectivity <= min_degree
    assert known.classify("vertex_connectivity <= edge_connectivity")["status"] == "known"
    assert known.classify("edge_connectivity <= min_degree")["status"] == "known"
    assert known.classify("vertex_connectivity <= min_degree")["status"] == "derived"
    # proven this session
    assert known.classify("radius <= matching_number")["status"] == "known"
    assert known.classify("degeneracy <= vertex_cover_number")["status"] == "known"


def test_distance_and_cover_invariants():
    from fractions import Fraction
    c5 = G.cycle(5)
    assert G.average_eccentricity(c5) == 2 and G.average_distance(c5) == Fraction(3, 2)
    assert G.total_domination_number(c5) == 3 and G.edge_cover_number(c5) == 3
    assert G.total_domination_number(G.complete(4)) == 2
    # radius <= average_eccentricity <= diameter on a path
    p6 = G.path(6)
    assert G.radius(p6) <= G.average_eccentricity(p6) <= G.diameter(p6)


def test_distance_cover_known_bounds():
    from matyos.discovery import known
    assert known.classify("radius <= average_eccentricity")["status"] == "known"
    assert known.classify("average_distance <= independence_number")["status"] == "known"  # Chung
    assert known.classify("independence_number <= edge_cover_number")["status"] == "known"
    # avg_distance <= edge_cover derives via Chung (avg_dist<=alpha) + alpha<=edge_cover
    assert known.classify("average_distance <= edge_cover_number")["status"] == "derived"


def test_radius_le_vertex_cover_holds(  ):
    # proven theorem (docs/conjectures/radius-le-vertex-cover.md); check it on the
    # sample plus paths, where equality radius == tau is attained.
    graphs = G.sample_graphs() + [G.path(n) for n in range(2, 12)]
    for g in graphs:
        assert G.radius(g) <= G.vertex_cover_number(g)
    for n in range(2, 12):                       # tight on paths: radius == tau
        p = G.path(n)
        assert G.radius(p) == G.vertex_cover_number(p)


def test_classified_search_tags_every_conjecture_candidates_first():
    res = G.classified_search()
    assert res and all(r["novelty"] in {"known", "derived", "candidate"} for r in res)
    # candidates (if any) are sorted ahead of known/derived
    order = [r["novelty"] for r in res]
    if "candidate" in order and "known" in order:
        assert order.index("candidate") < order.index("known")


import pytest
spectral = pytest.mark.skipif(not G.HAVE_SPECTRAL, reason="spectral needs mpmath")


@spectral
def test_spectral_radius_known_values():
    assert G.spectral_radius(G.complete(4)) == pytest.approx(3.0)   # K_n -> n-1
    assert G.spectral_radius(G.cycle(5)) == pytest.approx(2.0)      # C_n -> 2
    assert G.algebraic_connectivity(G.complete(4)) == pytest.approx(4.0)  # K_n -> n


@spectral
def test_graffiti_rediscovers_spectral_bracket():
    conj = {c.text for c in G.graffiti_search()}
    # classic: avg_degree <= spectral_radius <= max_degree
    assert "avg_degree <= spectral_radius" in conj
    assert "spectral_radius <= max_degree" in conj
    assert "laplacian_spectral_radius <= order" in conj
