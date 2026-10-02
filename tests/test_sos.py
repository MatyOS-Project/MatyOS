"""Tests for the SOS certificate engine (matyos.discovery.sos).

The contract is SOUNDNESS: it must never certify a false inequality. These tests
check that, plus coverage of the classic power-mean chain and the judge->TRUE
promotion.
"""
import random

from matyos.discovery import sos, stoqos
from matyos.discovery import domains as D


def test_certifies_the_power_mean_chain():
    # min <= HM <= GM <= AM <= RMS <= max, all proven
    chain = ["vmin", "harmean", "geomean", "mean", "rms", "vmax"]
    for i in range(len(chain)):
        for j in range(i + 1, len(chain)):
            assert sos.certify(chain[i], chain[j]) is not None
    # the famous ones carry an explicit SOS witness
    assert "AM–GM" in sos.certify("geomean", "mean")
    assert "QM–AM" in sos.certify("mean", "rms")


def test_declines_non_theorems():
    # not universally true -> must NOT be certified
    for a, b in [("mean", "geomean"), ("vmax", "mean"), ("vmin", "halfmax"),
                 ("twicemin", "vmax"), ("mean", "median"), ("median", "mean")]:
        assert sos.certify(a, b) is None


def test_soundness_on_random_battery():
    # every certified pair must actually hold on every positive vector — no exceptions
    F = D._number_means_domain().functionals
    names = list(F)
    rng = random.Random(7)
    battery = [[rng.randint(1, 40) for _ in range(rng.randint(3, 7))] for _ in range(1500)]
    vals = {n: [float(F[n](v)) for v in battery] for n in names}
    for a in names:
        for b in names:
            if a != b and sos.certify(a, b) is not None:
                assert all(vals[a][i] <= vals[b][i] + 1e-9 for i in range(len(battery))), \
                    f"UNSOUND: certified {a} <= {b} but it fails on evidence"


def test_judge_domain_promotes_proven_to_true():
    tri = D._number_means_domain()
    j = stoqos.judge_domain(tri, "geomean <= mean")       # AM-GM
    assert j.verdict == "true" and j.certificate is not None
    assert stoqos.truth3(j) == "true"
    assert j.value == 1.0 and j.backend == "sos"
    # a false means bound is still FALSE (counterexample), never proven
    assert stoqos.judge_domain(tri, "mean <= vmin").verdict == "false"


def test_certificate_defaults_none():
    j = stoqos.Judgement("realistic", 0.7, 0.8, False, "m", "n")
    assert j.certificate is None
    assert stoqos.truth3(stoqos.Judgement("true", 1.0, 1.0, True, "sos", "p", "proof")) == "true"
