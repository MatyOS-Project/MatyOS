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
