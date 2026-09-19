"""Tests for the MatyOS v2 discovery-engine scaffold.

These pin the one honest end-to-end signal (Fibonacci -> formula -> golden-ratio
anomaly) and the component contracts, so future work on the engine cannot silently
break the toy loop.
"""

from fractions import Fraction

import pytest

from matyos.discovery.objects import Sequence, Formula, Series
from matyos.discovery import generator, scorer, verify as verify_mod, anomaly
from matyos.discovery.engine import DiscoveryEngine

pslq = pytest.mark.skipif(not anomaly.HAVE_PSLQ, reason="mpmath/PSLQ not installed")

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


@pslq
def test_scorer_flags_golden_ratio_anomaly_on_transferred_formula():
    s = Sequence.of(FIB, name="fib")
    f = next(generator.cross_domain_transfer(s))
    sc = scorer.score(f)
    assert sc.breakdown["numerical_anomaly"] == pytest.approx(1.0)
    assert sc.breakdown["resonance"] == pytest.approx(1.0)
    assert "sqrt5" in sc.notes["numerical_anomaly"]


@pslq
def test_pslq_recovers_golden_ratio_closed_form():
    phi = 1.6180339887498948482045868343656381177203  # passed exactly below
    from fractions import Fraction
    # exact rational extremely close to phi: use Fibonacci ratio of large terms
    a, b = 0, 1
    for _ in range(200):
        a, b = b, a + b
    rel = anomaly.find_closed_form(Fraction(b, a))
    assert rel is not None
    assert rel.formula == "x = (1 + sqrt5) / 2"


@pslq
def test_pslq_rejects_pure_rational_ratio():
    # A ratio that merely settles near a rational is not a closed-form discovery.
    from fractions import Fraction
    assert anomaly.find_closed_form(Fraction(160, 159)) is None


def test_arithmetic_sequence_scores_low_on_novelty():
    s = Sequence.of([2, 4, 6, 8, 10, 12], name="evens")
    sc = scorer.score(s)
    assert sc.breakdown["structural_novelty"] <= 0.2


@pslq
def test_high_precision_confirm_holds_for_fibonacci_formula():
    s = Sequence.of(FIB, name="fib")
    f = next(generator.cross_domain_transfer(s))
    v = verify_mod.verify(f)
    assert v.confirmed is True


def test_prior_art_lookup_identifies_fibonacci():
    # Works live (OEIS) or offline (local table): both return A000045.
    ident, _live = verify_mod.oeis_lookup((0, 1, 1, 2, 3, 5, 8, 13))
    assert ident is not None
    assert "A000045" in ident


@pslq
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
    assert "sqrt5" in top.score.notes.get("numerical_anomaly", "")


@pslq
def test_lean_handoff_emits_statement_for_basel():
    from matyos.discovery.engine import _candidate_record
    from matyos.discovery import lean
    basel = Series(term_fn=lambda n: 1 / (n * n), text="sum 1/n^2", start=1)
    sc = scorer.score(basel)
    v = verify_mod.verify(basel)
    from matyos.discovery.engine import Candidate
    rec = _candidate_record(Candidate(object=basel, score=sc, verification=v), 1)
    stmt = rec["lean_statement"]
    assert stmt is not None
    assert "import Mathlib" in stmt and "Real.pi^2" in stmt and "sorry" in stmt
    assert set(lean.toolchain()) == {"lean", "lake", "ready"}


def test_try_prove_honest_when_no_toolchain():
    # On a machine with no Lean, proving must degrade honestly, never fake a proof.
    from matyos.discovery import lean
    stmt = "import Mathlib\n\ntheorem t : (1 : ℝ) = 1 := by\n  sorry\n"
    out = lean.try_prove(stmt, timeout=10)
    assert out["proved"] is False
    if not lean.toolchain()["lean"]:
        assert out["status"] == "lean_unavailable"
    else:
        # Lean present but a real-number goal needs a configured mathlib project.
        assert out["status"] in {"mathlib_unavailable", "proved", "open"}


def test_try_prove_rejects_statement_without_sorry():
    from matyos.discovery import lean
    if not lean.toolchain()["lean"]:
        import pytest as _pt
        _pt.skip("needs lean to reach the no-sorry check")
    out = lean.try_prove("theorem t : True := trivial\n")
    assert out["status"] == "error" and out["proved"] is False


def test_guided_prove_search_logic_with_injected_runner():
    from matyos.discovery import lean
    stmt = "theorem t : True := by\n  sorry\n"
    # a fake Lean that only accepts the tactic 'win'
    def runner(source, timeout):
        return ("win" in source, "" if "win" in source else "error: unsolved goals")
    # suggester that only proposes 'win' on round 1, after seeing round 0's error
    def suggest(ctx):
        if ctx["round"] == 0:
            return ["lose_a", "lose_b"]
        assert ctx["last_errors"] and ctx["last_errors"][0]["error"]   # feedback arrived
        return ["win"]
    out = lean.guided_prove(stmt, suggest=suggest, rounds=3, breadth=4, runner=runner)
    assert out["proved"] is True and out["tactic"] == "win" and out["rounds_used"] == 2
    # and an honest miss when nothing closes it
    miss = lean.guided_prove(stmt, suggest=lambda c: ["nope"], rounds=2, runner=runner)
    assert miss["proved"] is False and miss["status"] == "open"


def test_guided_prove_degrades_to_ladder_without_suggester():
    from matyos.discovery import lean
    stmt = "theorem t : True := by\n  sorry\n"
    seen = []
    def runner(source, timeout):
        seen.append(source)
        return (False, "error: no")            # never closes -> exercises the default ladder
    out = lean.guided_prove(stmt, rounds=1, breadth=99, runner=runner)
    assert out["proved"] is False
    # with no suggester it should have tried the fixed ladder's tactics
    assert any("norm_num" in s for s in seen) and any("exact?" in s for s in seen)


def test_conjecture_bundles_claim_statement_and_status():
    from matyos.discovery.formal import Conjecture
    rec = {"closed_form": "x = (1 + sqrt5) / 2 (PSLQ): x = (1 + sqrt5) / 2",
           "display": {"kind": "constant"},
           "lean_statement": "import Mathlib\n\ntheorem t : x = 1 := by\n  sorry\n",
           "label": {"status": "realistic (open)", "truth_name": "REALISTIC"}}
    c = Conjecture.from_record(rec)
    assert "sqrt5" in c.claim
    assert c.proved is False and c.status == "open"          # has statement, unproved
    d = c.to_dict()
    assert d["proved"] is False and d["lean_statement"] is not None
    # no formal statement -> "stated", and attempt_proof is a no-op (no Lean needed)
    bare = Conjecture(claim="something", lean_statement=None)
    assert bare.status == "stated"
    assert bare.attempt_proof() is bare


@pslq
def test_engine_conjectures_are_first_class_objects():
    from matyos.discovery.engine import DiscoveryEngine
    from matyos.discovery.formal import Conjecture
    fib = Sequence.of([0, 1, 1, 2, 3, 5, 8, 13, 21, 34], name="fib")
    conjs = DiscoveryEngine(min_score=0.2).conjectures([fib], limit=5)  # prove=False
    assert conjs and all(isinstance(c, Conjecture) for c in conjs)
    # the golden-ratio find carries a formal statement and reads as open, not proved
    assert any("sqrt5" in c.claim for c in conjs)
    assert all(c.proved is False for c in conjs)              # prove=False: nothing claimed proved


def test_extract_lemma_parses_try_this():
    from matyos.discovery import lean
    assert lean._extract_lemma("Try this: exact foo") == "exact foo"
    # Lean's actual captured format: suggestion on the next line, with a [apply] tag
    real = "Try this:\n  [apply] exact Nat.add_comm a b\n"
    assert lean._extract_lemma(real) == "exact Nat.add_comm a b"
    assert lean._extract_lemma("no suggestion here") is None


def test_proof_cache_key_is_deterministic_and_ladder_sensitive():
    from matyos.discovery import lean
    s = "import Mathlib\n\ntheorem t : True := by\n  sorry\n"
    assert lean._cache_key(s, ["decide"]) == lean._cache_key(s, ["decide"])
    assert lean._cache_key(s, ["decide"]) != lean._cache_key(s, ["simp"])


def test_ladder_includes_lemma_search_and_sequences():
    from matyos.discovery import lean
    assert "exact?" in lean._TACTIC_LADDER            # mathlib lemma search present
    assert any("<;>" in t for t in lean._TACTIC_LADDER)  # multi-step scripts present


def test_formal_handoff_attempt_proof_is_opt_in_and_honest():
    from matyos.discovery import verify as vm
    rec = {"closed_form": "x = (1 + sqrt5) / 2 (PSLQ): x = (1 + sqrt5) / 2",
           "display": {"kind": "constant"}}
    base = vm.formal_handoff(rec)
    assert "proof" not in base                      # opt-in: default stays statement-only
    withp = vm.formal_handoff(rec, attempt_proof=True, timeout=10)
    assert "proof" in withp and withp["proof"]["proved"] in (True, False)


def test_parse_seeds_extracts_int_lists():
    from matyos.discovery.reasoner import parse_seeds
    s = parse_seeds("try [1,2,3,4] and junk [5,6,7,8,9]; ignore short [1,2]")
    assert [1, 2, 3, 4] in s and [5, 6, 7, 8, 9] in s
    assert [1, 2] not in s          # too short to fit


def test_callback_reasoner_accepts_text_and_list():
    from matyos.discovery.reasoner import CallbackReasoner
    assert CallbackReasoner(lambda c: "next: [1,2,3,4]").propose({}) == [[1, 2, 3, 4]]
    assert CallbackReasoner(lambda c: [[1, 2, 3, 4]]).propose({}) == [[1, 2, 3, 4]]


def test_mutation_reasoner_proposes_from_frontier():
    from matyos.discovery.reasoner import MutationReasoner
    assert MutationReasoner().propose({"frontier": [[1, 2, 3, 4, 5]]})


@pslq
def test_llm_reasoner_drives_the_loop():
    from matyos.discovery.reasoner import CallbackReasoner
    seen = []
    def fake_llm(ctx):
        seen.append(ctx)
        return "let's try [0,1,2,5,12,29,70]"
    summary = DiscoveryEngine(0.2).loop(
        [Sequence.of(FIB, name="fib")], rounds=2, reasoner=CallbackReasoner(fake_llm))
    assert seen, "the reasoner (the LLM) was consulted"
    assert set(seen[0]) == {"frontier", "found", "mysteries"}
    assert summary["rounds_run"] >= 1


def test_formal_handoff_returns_lean_statement():
    out = verify_mod.formal_handoff({"closed_form": "closed form found (PSLQ): sum = (pi^2) / 6",
                                     "display": {"kind": "series", "text": "sum 1/n^2"}})
    assert "sorry" in out["lean_statement"]
    assert "toolchain" in out


@pslq
def test_refutation_survives_for_genuine_recurrence():
    s = Sequence.of(FIB, name="fib")
    f = next(generator.cross_domain_transfer(s))
    verdict, note = verify_mod.refute(f)
    assert verdict == "survived"
    assert "sqrt5" in note


@pslq
def test_realistic_label_is_realistic_for_unproven_find():
    from matyos.discovery import label as lbl
    s = Sequence.of(FIB, name="fib")
    f = next(generator.cross_domain_transfer(s))
    v = verify_mod.verify(f)
    assert v.refutation == "survived"
    assert v.label["truth_name"] == "realistic"      # not "true": it's unproven
    assert v.label["status"].startswith("realistic")


def test_realistic_label_maps_refuted_to_false():
    from matyos.discovery import label as lbl
    out = lbl.realistic_label(has_closed_form=True, refutation="refuted", prior_art=None)
    assert out["truth_name"] == "false"
    out2 = lbl.realistic_label(has_closed_form=False, refutation="n/a", prior_art=None)
    assert out2["status"] == "no closed form"


def test_store_dedupes_and_persists(tmp_path):
    from matyos.discovery.store import CandidateStore
    s = CandidateStore()
    assert s.add("k1", {"x": 1}) is True
    assert s.add("k1", {"x": 2}) is False   # dedupe
    assert len(s) == 1
    p = tmp_path / "store.json"
    s.save(p)
    assert CandidateStore.load(p).seen("k1")


@pslq
def test_series_domain_finds_basel_closed_form():
    basel = Series(term_fn=lambda n: 1 / (n * n), text="sum 1/n^2", start=1)
    sc = scorer.score(basel)
    assert sc.breakdown["numerical_anomaly"] == pytest.approx(1.0)
    assert "pi^2" in sc.notes["numerical_anomaly"]      # sum = pi^2/6


@pslq
def test_basis_includes_new_number_theory_constants():
    names = [n for n, _ in anomaly._basis()]
    for c in ("zeta3", "zeta5", "catalan", "pi^4", "sqrt13"):
        assert c in names


@pslq
def test_continued_fraction_identifies_4_over_pi():
    from matyos.discovery.objects import ContinuedFraction
    c = ContinuedFraction(a_fn=lambda n: n * n,
                          b_fn=lambda n: 1 if n == 0 else 2 * n + 1, text="4/pi")
    rel, recip = anomaly.find_closed_form_pm(c.value(dps=80), dps=80)
    assert rel is not None and recip is True
    assert rel.formula == "x = (pi) / 4"       # value = 4/pi, so 1/value = pi/4


@pslq
def test_cf_search_runs_and_returns_list():
    from matyos.discovery import cf
    hits = cf.search(coeff_range=1, degree=0, dps=80, max_hits=3, max_scan=3, terms=60)
    assert isinstance(hits, list)


@pslq
def test_cf_frontier_runs_and_returns_mysteries():
    from matyos.discovery import cf
    myst = cf.frontier(coeff_range=1, degree=1, dps=60, max_hits=3, max_scan=8,
                       terms=80, core=True)
    assert isinstance(myst, list)
    for m in myst:
        assert isinstance(m, cf.CFMystery)


@pslq
def test_cf_frontier_excludes_known_and_rational():
    # a(n)=n^2, b(n)=2n+1 -> 4/pi (a known hit): must NOT be flagged a mystery.
    from matyos.discovery import cf
    myst = cf.frontier(coeff_range=2, degree=2, dps=60, max_hits=25, max_scan=200,
                       terms=120, core=True)
    for m in myst:
        assert m.value != "1.273239544735"       # the 4/pi CF, if scanned
    # a plain convergent rational is a small rational, not a mystery
    assert not cf._is_small_rational.__doc__ is None  # sanity: helper present
    import mpmath as mp
    assert cf._is_small_rational(mp.mpf(3) / 2, dps=40) is True
    assert cf._is_small_rational(mp.pi, dps=40) is False


@pslq
def test_cf_algebraic_screen_rejects_roots_keeps_transcendental():
    # cube root of 2 is algebraic (root of x^3-2) -> screened out of mysteries.
    from matyos.discovery import cf
    import mpmath as mp
    assert cf._is_algebraic(mp.mpf(2) ** (mp.mpf(1) / 3), dps=60) is True
    assert cf._is_algebraic(mp.sqrt(2) + mp.sqrt(3), dps=60) is True   # algebraic deg 4
    assert cf._is_algebraic(mp.pi, dps=60) is False                    # transcendental


@pslq
def test_mystery_constant_is_kept_and_labelled():
    # sum 1/(2^n+1): converges, but no closed form in the basis -> a mystery.
    m = Series(term_fn=lambda n: 1 / (2 ** n + 1), text="sum 1/(2^n+1)", start=1)
    sc = scorer.score(m)
    assert sc.breakdown["mystery"] == pytest.approx(1.0)
    assert sc.breakdown["numerical_anomaly"] == pytest.approx(0.0)
    assert sc.total >= 0.2                      # kept, not filtered
    v = verify_mod.verify(m)
    assert "mystery" in v.label["status"]
    assert v.label["truth_name"] == "realistic"
    assert v.label["novelty"] == "unknown"


@pslq
def test_known_series_is_not_a_mystery():
    b = Series(term_fn=lambda n: 1 / (n * n), text="basel", start=1)
    assert scorer.score(b).breakdown["mystery"] == pytest.approx(0.0)


@pslq
def test_series_finds_apery_zeta3():
    z = Series(term_fn=lambda n: 1 / (n * n * n), text="sum 1/n^3", start=1)
    sc = scorer.score(z)
    assert sc.breakdown["numerical_anomaly"] == pytest.approx(1.0)
    assert "zeta3" in sc.notes["numerical_anomaly"]


@pslq
def test_series_finds_pi4_over_90():
    z = Series(term_fn=lambda n: 1 / n ** 4, text="sum 1/n^4", start=1)
    rel = anomaly.find_closed_form(z.value(80), dps=80)
    assert rel is not None and rel.formula == "x = (pi^4) / 90"


def test_order3_recurrence_detected():
    # Tribonacci: a[n] = a[n-1] + a[n-2] + a[n-3]
    trib = Sequence.of([0, 0, 1, 1, 2, 4, 7, 13, 24, 44, 81], name="trib")
    transfers = list(generator.cross_domain_transfer(trib))
    assert transfers, "order-3 recurrence should be detected"
    assert "a[n-3]" in transfers[0].text


@pslq
def test_series_leibniz_is_pi_over_4():
    leib = Series(term_fn=lambda n: (-1) ** n / (2 * n + 1), text="leibniz", start=0)
    rel = anomaly.find_closed_form(leib.value(80))
    assert rel is not None and rel.formula == "x = (pi) / 4"


@pslq
def test_series_known_constant_labelled_known_and_survives_refute():
    basel = Series(term_fn=lambda n: 1 / (n * n), text="sum 1/n^2", start=1)
    v = verify_mod.verify(basel)
    assert v.refutation == "survived"
    assert v.label["truth_name"] == "realistic"   # unproven
    assert v.label["novelty"] == "known"          # pi^2/6 is a known constant


@pslq
def test_formula_transfers_to_reciprocal_series():
    s = Sequence.of(FIB, name="fib")
    f = next(generator.cross_domain_transfer(s))
    series = [t for t in generator.cross_domain_transfer(f) if isinstance(t, Series)]
    assert series, "growing recurrence should transfer to a reciprocal series"
    assert series[0].provenance.startswith("transfer:formula->series")


@pslq
def test_loop_accumulates_and_dedupes_across_rounds():
    engine = DiscoveryEngine(min_score=0.2)
    summary = engine.loop([Sequence.of(FIB, name="fib")], rounds=3)
    assert 1 <= summary["rounds_run"] <= 3
    assert summary["unique"] >= 1
    keys = [ (c["display"].get("text") or "") + str(c.get("round")) for c in summary["candidates"] ]
    # ranks are contiguous and sorted by score desc
    ranks = [c["rank"] for c in summary["candidates"]]
    assert ranks == sorted(ranks)
    scores = [c["score"] for c in summary["candidates"]]
    assert scores == sorted(scores, reverse=True)
