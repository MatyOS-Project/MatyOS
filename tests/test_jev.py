"""Tests for the Jev promise-scorer (matyos.discovery.jev).

All offline: they exercise the heuristic fallback, the rerank ordering, the
request-payload shape and the response parser. The live Jev backend needs a key
(MATYOS_JEV_API_KEY) and is not exercised here.
"""

from matyos.discovery import jev, graph


def test_no_key_uses_heuristic(monkeypatch):
    monkeypatch.delenv("MATYOS_JEV_API_KEY", raising=False)
    assert jev.configured() is False
    p = jev.promise_graph({"statement": "radius <= diameter", "held_on": 100,
                           "tight_on": 40, "novelty": "candidate"})
    assert p.backend == "heuristic"
    assert 0.0 <= p.value <= 1.0


def test_tightness_and_novelty_order_the_score(monkeypatch):
    monkeypatch.delenv("MATYOS_JEV_API_KEY", raising=False)
    base = {"statement": "a <= b", "held_on": 100, "novelty": "candidate"}
    tight = jev.promise_graph({**base, "tight_on": 90})
    loose = jev.promise_graph({**base, "tight_on": 5})
    assert tight.value > loose.value                      # tight bounds are more promising
    # an explained (known) bound scores below a candidate with identical stats
    known_row = jev.promise_graph({**base, "tight_on": 90, "novelty": "known"})
    assert known_row.value < tight.value


def test_rerank_keeps_tiers_and_orders_by_promise(monkeypatch):
    monkeypatch.delenv("MATYOS_JEV_API_KEY", raising=False)
    rows = [
        {"statement": "c1", "held_on": 100, "tight_on": 5,  "novelty": "candidate"},
        {"statement": "c2", "held_on": 100, "tight_on": 95, "novelty": "candidate"},
        {"statement": "k1", "held_on": 100, "tight_on": 95, "novelty": "known"},
    ]
    out = jev.rerank(rows)
    assert all("promise" in r and "promise_backend" in r for r in out)
    # candidates come before the known tier...
    assert [r["statement"] for r in out][:2] == ["c2", "c1"]   # tighter candidate first
    assert out[-1]["statement"] == "k1"


def test_build_request_is_a_noul_question():
    req = jev.build_request({"statement": "a <= b"})
    assert req["questions"]["promise"]["type"] == "noul"
    assert "state" in req and "model" in req


def test_parse_answer_handles_float_and_object():
    assert jev._parse_answer({"answers": {"promise": 0.8}}) == (0.8, 1.0)
    assert jev._parse_answer(
        {"answers": {"promise": {"probability": 0.7, "confidence": 0.6}}}) == (0.7, 0.6)
    assert jev._parse_answer({"nope": 1}) is None


def test_classified_search_score_flag(monkeypatch):
    monkeypatch.delenv("MATYOS_JEV_API_KEY", raising=False)
    rows = graph.classified_search(score=True)
    assert rows and all("promise" in r for r in rows)
    assert all(r["promise_backend"] == "heuristic" for r in rows)
