"""Tests for the hard-problems honest engagement layer.

These are fast (no Lean, no PSLQ needed for the finite verifiers). They lock in the
central promise: MatyOS states/verifies-finite/explores/tracks, and NEVER reports a
famous conjecture as proved.
"""

import pytest

from matyos.problems import famous as F


def test_registry_has_four_and_none_provable():
    assert set(F.REGISTRY) == {"goldbach", "twin_primes", "collatz", "riemann"}
    for p in F.REGISTRY.values():
        assert p.provable_by_matyos is False          # hard-coded, structural honesty


def test_state_returns_open_conjecture_never_proved():
    for key in F.REGISTRY:
        c = F.state(key)
        assert c.source == "famous-problem"
        assert c.proved is False and c.status != "proved"
        assert c.label["provable_by_matyos"] is False
        assert "sorry" in c.lean_statement


def test_goldbach_finite_verification_is_evidence_not_proof():
    ev = F.verify_finite("goldbach", 1000)
    assert ev.holds is True and ev.counterexample is None
    assert "NOT a proof" in repr(ev)                  # never masquerades as a proof


def test_collatz_finite_verification():
    ev = F.verify_finite("collatz", 500)
    assert ev.holds is True and "NOT a proof" in repr(ev)


def test_twin_and_riemann_reject_finite_checks_honestly():
    with pytest.raises(ValueError):
        F.verify_finite("twin_primes", 1000)          # infinitude — no finite check
    with pytest.raises(ValueError):
        F.verify_finite("riemann", 1000)              # no zeta representation


def test_adjacent_sequences_are_real():
    # 8 twin-pair lower members below 100: 3,5,11,17,29,41,59,71
    assert F._adjacent_sequence("twin_primes", 100) == [3, 5, 11, 17, 29, 41, 59, 71]
    # Collatz stopping times: n=1 -> 0 steps, n=2 -> 1, n=3 -> 7
    st = F._adjacent_sequence("collatz", 3)
    assert st == [0, 1, 7]


def test_status_reports_capabilities_honestly():
    s = F.status("riemann")
    assert s["provable_by_matyos"] is False
    assert "cannot" not in s  # key is matyos_cannot
    assert "represent" in s["matyos_cannot"]          # the honest limit is stated
