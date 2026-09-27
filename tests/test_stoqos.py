"""Tests for Stoqos, the calibrated REALISTIC-level model.

All fast/offline: a tiny synthetic fit, the feature extractor, persistence, a
small grounded dataset, and the honesty guards on realistic_score. The full
train_default (heavy battery) is exercised separately, not here.
"""

from matyos.discovery import stoqos, graph as G


def test_logistic_fit_separates_synthetic():
    # feature 0 perfectly separates; others noise-free zero
    X = [[3, 0, 0, 0, 0, 0, 0] for _ in range(8)] + \
        [[-3, 0, 0, 0, 0, 0, 0] for _ in range(8)]
    y = [1] * 8 + [0] * 8
    m = stoqos.Stoqos().fit(X, y, iters=2000)
    hi = m.predict_proba(dict(zip(stoqos.FEATURES, [3, 0, 0, 0, 0, 0, 0])))
    lo = m.predict_proba(dict(zip(stoqos.FEATURES, [-3, 0, 0, 0, 0, 0, 0])))
    assert hi > 0.8 and lo < 0.2
    assert 0.0 <= hi <= 1.0 and 0.0 <= lo <= 1.0


def test_features_tight_vs_strict():
    tight = stoqos.features_from_values([1, 2, 3], [1, 2, 3])   # equality everywhere
    strict = stoqos.features_from_values([1, 1, 1], [5, 6, 7])  # wide slack
    assert tight["tight_ratio"] == 1.0 and tight["min_margin"] == 0.0
    assert strict["tight_ratio"] == 0.0 and strict["min_margin"] > 0.0


def test_persistence_round_trip():
    X = [[2, 0, 0, 0, 0, 0, 0]] * 4 + [[-2, 0, 0, 0, 0, 0, 0]] * 4
    y = [1, 1, 1, 1, 0, 0, 0, 0]
    m = stoqos.Stoqos().fit(X, y, iters=500)
    m2 = stoqos.Stoqos.from_dict(m.to_dict())
    f = dict(zip(stoqos.FEATURES, [2, 0, 0, 0, 0, 0, 0]))
    assert abs(m.predict_proba(f) - m2.predict_proba(f)) < 1e-9


def test_build_dataset_small_is_labelled():
    strong = G.sample_graphs()[:16]
    X, y, pairs = stoqos.build_dataset(strong=strong, n_batteries=3,
                                       weak_size=8, seed=3)
    assert len(X) == len(y) == len(pairs) and len(X) > 0
    assert all(v in (0, 1) for v in y)
    assert set(X[0].keys()) == set(stoqos.FEATURES)


def _rich(**kw):
    d = {k: 0.0 for k in stoqos.FEATURES_RICH}
    d.update(kw)
    return d


def test_rich_features_shape_and_sanity():
    tight = stoqos.rich_features_from_values([1, 2, 3], [1, 2, 3])
    strict = stoqos.rich_features_from_values([1, 1, 1], [5, 6, 7])
    assert set(tight) == set(stoqos.FEATURES_RICH)
    assert tight["tight_ratio"] == 1.0 and strict["strict_ratio"] == 1.0


def test_mlp_learns_and_calibrates():
    X = [_rich(corr_ab=1.0, mean_margin=0.5) for _ in range(40)] + \
        [_rich(corr_ab=-1.0, mean_margin=-0.5) for _ in range(40)]
    y = [1] * 40 + [0] * 40
    net = stoqos.StoqosNet().fit(X, y, epochs=200, hidden=12, lr=0.1, seed=1)
    hi = net.predict_proba(_rich(corr_ab=1.0, mean_margin=0.5))
    lo = net.predict_proba(_rich(corr_ab=-1.0, mean_margin=-0.5))
    assert hi > 0.8 > lo
    net.calibrate(X, y)
    assert 0.4 <= net.T <= 4.0


def test_mlp_persistence_round_trip():
    X = [_rich(corr_ab=1.0)] * 6 + [_rich(corr_ab=-1.0)] * 6
    net = stoqos.StoqosNet().fit(X, [1] * 6 + [0] * 6, epochs=60, hidden=6, seed=2)
    net2 = stoqos.StoqosNet.from_dict(net.to_dict())
    f = _rich(corr_ab=1.0)
    assert abs(net.predict_proba(f) - net2.predict_proba(f)) < 1e-9


def test_judge_typed_api():
    r = stoqos.judge("radius <= diameter")
    assert r.verdict == "realistic" and 0.0 <= r.value <= 1.0 and 0.0 <= r.confidence <= 1.0
    f = stoqos.judge("diameter <= radius")          # fails on evidence
    assert f.verdict == "false" and f.value is None
    u = stoqos.judge("not_an_invariant <= diameter")
    assert u.verdict == "unknown" and u.value is None
    # a known theorem is flagged as such (Whitney κ<=δ is in the known DB)
    k = stoqos.judge("vertex_connectivity <= min_degree")
    assert k.known is True
    batch = stoqos.judge_batch(["radius <= diameter", "diameter <= radius"])
    assert len(batch) == 2 and batch[0].verdict == "realistic"


def test_model_robustness_never_crashes():
    assert stoqos.judge("foo <= bar").verdict == "unknown"          # out of domain
    m = stoqos.evidence_model()
    assert stoqos.score_evidence([1, 2], [3], model=m) is None       # length mismatch
    assert stoqos.score_evidence([], [], model=m) is None            # empty
    assert set(stoqos.rich_features_from_values([], [])) == set(stoqos.FEATURES_RICH)
    untrained = stoqos.StoqosNet()
    assert untrained.predict_proba({k: 0.0 for k in stoqos.FEATURES_RICH}) == 0.5


def test_meta_round_trip():
    net = stoqos.StoqosNet()
    net.meta = {"model": "stoqos", "domains": ["graphs"]}
    r = stoqos.StoqosNet.from_dict(net.to_dict())
    assert r.meta == {"model": "stoqos", "domains": ["graphs"]}


def test_shipped_model_is_self_describing():
    m = stoqos.evidence_model()
    assert m is not None and m.meta.get("model") == "stoqos"
    assert "heldout_auc_per_domain" in m.meta and "note" in m.meta


def test_domains_have_both_classes():
    from matyos.discovery import domains as D
    for dom in (D._sequence_domain(), D._number_theory_domain(),
                D._number_means_domain(), D._triangle_domain()):
        X, y, pairs = stoqos.build_domain_dataset(dom, n_batteries=10, seed=3)
        assert len(X) > 0 and set(y) <= {0, 1}
        assert 0 < sum(y) < len(y)              # genuine label variation
        assert len(set(pairs)) > 1


def test_truth3_three_valued():
    # the paper's logic: TRUE (proven) / FALSE / REALISTIC (held, unproven) / UNKNOWN
    J = stoqos.Judgement
    assert stoqos.truth3(J("realistic", 0.9, 0.9, True, "m", "")) == "true"    # known -> TRUE
    assert stoqos.truth3(J("realistic", 0.9, 0.9, False, "m", "")) == "realistic"
    assert stoqos.truth3(J("uncertain", 0.6, 0.6, False, "m", "")) == "realistic"  # still held
    assert stoqos.truth3(J("false", None, 1.0, False, "m", "")) == "false"
    assert stoqos.truth3(J("unknown", None, 0.0, False, "m", "")) == "unknown"
    # end to end: a known theorem reads as TRUE, a counterexample as FALSE
    assert stoqos.truth3(stoqos.judge("radius <= diameter")) == "true"
    assert stoqos.truth3(stoqos.judge("diameter <= radius")) == "false"


def test_judge_domain_triangles():
    from matyos.discovery import domains as D
    tri = D._triangle_domain()
    # Euler's inequality 2r <= R holds on every triangle -> not FALSE, not UNKNOWN
    euler = stoqos.judge_domain(tri, "tworadius <= circumradius")
    assert euler.verdict in ("realistic", "uncertain")
    # a bound with counterexamples on the strong battery -> FALSE
    bad = stoqos.judge_domain(tri, "longest <= shortest")
    assert bad.verdict == "false" and bad.value is None
    # a functional that isn't in the domain -> UNKNOWN, never a crash
    oo = stoqos.judge_domain(tri, "radius <= not_a_functional")
    assert oo.verdict == "unknown" and oo.value is None


def test_benchmark_structure():
    from matyos.discovery import domains as D
    fast = [D._sequence_domain(), D._number_theory_domain(), D._number_means_domain()]
    bm = stoqos.benchmark(domains=fast, n_batteries=6)
    assert set(bm) == {"per_domain", "transfer", "joint"}
    for name in ("sequences", "number_theory", "means"):
        assert name in bm["per_domain"] and name in bm["joint"]
        assert "pair_disjoint_auc" in bm["per_domain"][name]


def test_score_evidence_domain_agnostic():
    X = [_rich(corr_ab=1.0, mean_margin=0.5)] * 6 + [_rich(corr_ab=-1.0, mean_margin=-0.5)] * 6
    net = stoqos.StoqosNet().fit(X, [1]*6 + [0]*6, features=stoqos.FEATURES_RICH,
                                 epochs=60, hidden=6, seed=3)
    p = stoqos.score_evidence([1, 2, 3], [2, 3, 4], model=net)     # holds -> scored
    assert p is not None and 0.0 <= p <= 1.0
    assert stoqos.score_evidence([5, 6], [1, 2], model=net) is None  # fails -> None


class _Stub:
    def __init__(self, p): self.p = p
    def predict_proba(self, feats): return self.p


def test_phase4_abstention():
    # a decisive prediction commits; a coin-flip abstains
    assert stoqos.judge("radius <= diameter", model=_Stub(0.95)).verdict == "realistic"
    assert stoqos.judge("radius <= diameter", model=_Stub(0.50)).verdict == "uncertain"


def test_selective_report_monotonic():
    class _P:
        def predict_proba(self, f): return f["p"]
    X = [{"p": 0.95}, {"p": 0.9}, {"p": 0.55}, {"p": 0.45}, {"p": 0.1}, {"p": 0.05}]
    y = [1, 1, 0, 0, 0, 0]                       # the 0.55 case is a wrong commit
    accs = [r["accuracy"] for r in stoqos.selective_report(_P(), X, y,
                                                           thresholds=(0.0, 0.2, 0.8))]
    assert accs == sorted(accs) and accs[-1] == 1.0     # abstaining only improves accuracy


def test_realistic_score_guards():
    X = [[2, 0, 0, 0, 0, 0, 0]] * 4 + [[-2, 0, 0, 0, 0, 0, 0]] * 4
    m = stoqos.Stoqos().fit(X, [1, 1, 1, 1, 0, 0, 0, 0], iters=300)
    # unknown invariant -> None (out of domain, not our call)
    assert stoqos.realistic_score("not_an_invariant <= diameter", model=m) is None
    # a bound that does NOT hold on the sample is FALSE, not realistic -> None
    assert stoqos.realistic_score("diameter <= radius", model=m) is None
    # a real, holding bound -> a probability in [0, 1]
    p = stoqos.realistic_score("radius <= diameter", model=m)
    assert p is not None and 0.0 <= p <= 1.0
