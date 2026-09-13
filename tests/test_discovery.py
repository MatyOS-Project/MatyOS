"""Tests for the MatyOS v2 discovery-engine scaffold.

These pin the one honest end-to-end signal (Fibonacci -> formula -> golden-ratio
anomaly) and the component contracts, so future work on the engine cannot silently
break the toy loop.
"""

from fractions import Fraction

import pytest

from matyos.discovery.objects import Sequence, Formula
from matyos.discovery import generator, scorer, verify as verify_mod
from matyos.discovery.engine import DiscoveryEngine


FIB = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]


def test_sequence_construction_and_key():
    s = Sequence.of(FIB, name="fib")
    assert s.domain == "sequence"
    assert s.terms[3] == Fraction(2)
    assert s.key().startswith("seq:")


def test_cross_domain_transfer_recovers_fibonacci_recurrence():
    s = Sequence.of(FIB, name="fib")
    transfers = list(generator.cross_domain_transfer(s))
    assert len(transfers) == 1
    f = transfers[0]
    assert isinstance(f, Formula)
    assert f.provenance.startswith("transfer:sequence->formula")
    # The recovered rule must reproduce the sequence it came from.
    assert f.evaluate_prefix(len(FIB)) == tuple(Fraction(v) for v in FIB)


def test_geometric_sequence_is_singular_under_order2_fit():
    # Pure geometric (powers of 2) makes the order-2 system singular -> no transfer.
    s = Sequence.of([1, 2, 4, 8, 16, 32], name="pow2")
    assert list(generator.cross_domain_transfer(s)) == []


def test_scorer_flags_golden_ratio_anomaly_on_transferred_formula():
    s = Sequence.of(FIB, name="fib")
    f = next(generator.cross_domain_transfer(s))
    sc = scorer.score(f)
    assert sc.breakdown["numerical_anomaly"] == pytest.approx(1.0)
    assert sc.breakdown["resonance"] == pytest.approx(1.0)
    assert "phi" in sc.notes["numerical_anomaly"]


def test_arithmetic_sequence_scores_low_on_novelty():
    s = Sequence.of([2, 4, 6, 8, 10, 12], name="evens")
    sc = scorer.score(s)
    assert sc.breakdown["structural_novelty"] <= 0.2


def test_high_precision_confirm_holds_for_fibonacci_formula():
    s = Sequence.of(FIB, name="fib")
    f = next(generator.cross_domain_transfer(s))
    v = verify_mod.verify(f)
    assert v.confirmed is True


def test_prior_art_lookup_identifies_fibonacci():
    s = Sequence.of(FIB, name="fib")
    v = verify_mod.verify(s)
    assert v.prior_art is not None
    assert "A000045" in v.prior_art


def test_engine_end_to_end_ranks_fibonacci_formula_first():
    engine = DiscoveryEngine(min_score=0.2)
    seeds = [
        Sequence.of(FIB, name="fib"),
        Sequence.of([2, 4, 6, 8, 10, 12], name="evens"),
    ]
    candidates = engine.run(seeds)
    assert candidates, "engine produced no candidates"
    top = max(candidates, key=lambda c: c.score.total)
    assert isinstance(top.object, Formula)
    assert "phi" in top.score.notes.get("numerical_anomaly", "")


def test_stubs_are_explicit():
    with pytest.raises(NotImplementedError):
        scorer.pslq_constant_match(None, [])
    with pytest.raises(NotImplementedError):
        verify_mod.formal_handoff(None)
