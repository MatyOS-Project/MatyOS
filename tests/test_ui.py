"""Fast tests for the local researcher console (matyos.ui).

Kept cheap: exercises the page and the light endpoints; avoids the heavy
classified_search / PSLQ paths (covered elsewhere) so the suite stays quick.
"""

import json
import threading
import time
import urllib.request
from http.server import HTTPServer

from matyos import ui


def _server():
    srv = HTTPServer(("127.0.0.1", 8758), ui._Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.3)
    return srv


def _get(path):
    return urllib.request.urlopen("http://127.0.0.1:8758" + path, timeout=30).read()


def _post(path, obj):
    req = urllib.request.Request("http://127.0.0.1:8758" + path,
                                 data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=30).read()


def test_page_and_light_endpoints():
    assert "research console" in ui._PAGE and "solve famous open problems" in ui._PAGE
    srv = _server()
    try:
        assert b"research console" in _get("/")
        probs = json.loads(_get("/api/problems"))["problems"]
        assert {p["name"] for p in probs} >= {"Riemann Hypothesis", "Collatz (3n+1) conjecture"}
        assert all(p["provable_by_matyos"] is False for p in probs)   # honesty carried to the UI
        # discover with too-few integers returns a note, no heavy compute
        out = json.loads(_post("/api/discover", {"seq": [1, 2]}))
        assert out["candidates"] == [] and "at least 4" in out["note"]
    finally:
        srv.shutdown()


def test_lab_endpoints():
    srv = _server()
    try:
        inv = json.loads(_get("/api/invariants"))["invariants"]
        assert "radius" in inv and "diameter" in inv and "total_domination_number" in inv
        # a probe that holds, with a novelty label
        r = json.loads(_post("/api/lab", {"a": "radius", "b": "diameter"}))
        assert r["holds"] is True and r["tested"] > 50 and r["novelty"] == "known"
        # same invariant twice is rejected
        assert "error" in json.loads(_post("/api/lab", {"a": "radius", "b": "radius"}))
    finally:
        srv.shutdown()
