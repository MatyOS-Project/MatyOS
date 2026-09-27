"""Jev promise-scorer — an optional, calibrated *search-ordering* layer.

Jev (TypeSafe AI) is a non-autoregressive "System One" model: instead of writing
text it returns a **typed value with a calibrated probability**. That shape is a
perfect fit for the one question MatyOS asks over and over during discovery:

    "Of these thousands of candidate bounds, which are worth the expensive
     experiment + Lean proof next?"

So Jev is wired in here as a **scorer only**. It reorders candidates; it never
decides truth. Every ordering it produces still flows into the unchanged pipeline
— stress-test battery, then the trusted Lean/kernel proof — and only the kernel
ever labels a statement TRUE. A miscalibrated or offline Jev can waste search
effort; it can never make MatyOS assert a falsehood.

Two backends:

* **jev**       — the real API, used when ``MATYOS_JEV_API_KEY`` is set. The key is
  read from the environment and never logged; the only thing sent is the maths
  (invariant names + support statistics), never user data.
* **heuristic** — a transparent, dependency-free fallback used when no key is
  configured (or the call fails), so MatyOS keeps working and stays testable.

The returned :class:`Promise` carries the value, Jev's confidence, the backend
used and a breakdown, so a human reads *why*, not just a number.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field

_ENV_KEY = "MATYOS_JEV_API_KEY"
_ENV_URL = "MATYOS_JEV_URL"          # full endpoint; default is unverified early-access
_ENV_MODEL = "MATYOS_JEV_MODEL"
_DEFAULT_URL = "https://api.typesafe.ai/v1/decide"
_DEFAULT_MODEL = "jev-1"
_TIMEOUT_S = 4.0

_NOVELTY_RANK = {"candidate": 0, "derived": 1, "known": 2}
_NOVELTY_PRIOR = {"candidate": 1.0, "derived": 0.20, "known": 0.05}


@dataclass(frozen=True)
class Promise:
    """A calibrated ordering signal in [0, 1]. NOT a truth judgement."""
    value: float
    confidence: float
    backend: str                       # "jev" | "heuristic"
    breakdown: dict = field(default_factory=dict)


def configured() -> bool:
    """True when a Jev API key is present in the environment."""
    return bool(os.environ.get(_ENV_KEY))


# --------------------------------------------------------------------------- #
# request construction (pure, unit-testable without any network)
# --------------------------------------------------------------------------- #
def _candidate_state(cand: dict) -> dict:
    """The maths we describe to Jev for one candidate bound. Maths only."""
    return {
        "statement": cand["statement"],
        "held_on": cand.get("held_on"),
        "tight_on": cand.get("tight_on"),
        "novelty": cand.get("novelty"),
        "domain": "graph_invariant_inequality",
    }


def build_request(state: dict) -> dict:
    """The JSON body sent to Jev: a single Noul question (one probability).

    Kept separate so tests can assert the payload shape without a live key.
    """
    return {
        "model": os.environ.get(_ENV_MODEL, _DEFAULT_MODEL),
        "state": state,
        "questions": {
            "promise": {
                "type": "noul",
                "prompt": ("Probability that this inequality is a genuinely new, "
                           "true, provable bound not already implied by known "
                           "graph theory."),
            }
        },
    }


def _parse_answer(payload: dict) -> tuple[float, float] | None:
    """Pull (probability, confidence) out of a Jev response, defensively.

    A Noul answer is documented as a single probability; some responses also
    carry a confidence. Accept a bare float or an object with either key.
    """
    try:
        ans = payload["answers"]["promise"]
    except (KeyError, TypeError):
        return None
    if isinstance(ans, (int, float)):
        return float(ans), 1.0
    if isinstance(ans, dict):
        p = ans.get("probability", ans.get("value"))
        if p is None:
            return None
        c = ans.get("confidence", 1.0)
        return float(p), float(c)
    return None


def _jev_call(state: dict) -> Promise | None:
    """Call the real Jev API. Returns None on missing key or any failure."""
    key = os.environ.get(_ENV_KEY)
    if not key:
        return None
    url = os.environ.get(_ENV_URL, _DEFAULT_URL)
    body = json.dumps(build_request(state)).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as r:  # noqa: S310
            payload = json.loads(r.read().decode())
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None                    # any trouble -> caller falls back
    parsed = _parse_answer(payload)
    if parsed is None:
        return None
    value, conf = parsed
    value = max(0.0, min(1.0, value))
    return Promise(value=value, confidence=max(0.0, min(1.0, conf)),
                   backend="jev", breakdown={"source": "typesafe/jev"})


# --------------------------------------------------------------------------- #
# heuristic fallback (transparent, deterministic, no network)
# --------------------------------------------------------------------------- #
def _heuristic(cand: dict) -> Promise:
    """A readable proxy for "worth proving next", from signals we already have.

    Candidates (bounds MatyOS's knowledge cannot explain) get the prior; a bound
    that is often *tight* (met with equality) and holds on wide support is the
    more promising kind — that is where a real, provable theorem tends to live.
    Derived/known bounds score low: they are already explained.
    """
    novelty = cand.get("novelty", "candidate")
    prior = _NOVELTY_PRIOR.get(novelty, 0.5)
    held = max(0, int(cand.get("held_on", 0) or 0))
    tight = max(0, int(cand.get("tight_on", 0) or 0))
    tight_ratio = (tight / held) if held else 0.0        # [0,1]
    support = min(1.0, held / 120.0)                      # saturates ~120 graphs
    # tightness dominates within a tier; support is a mild robustness bonus.
    value = prior * (0.30 + 0.55 * tight_ratio + 0.15 * support)
    value = max(0.0, min(1.0, value))
    return Promise(
        value=value,
        confidence=0.5,               # a heuristic is only mildly sure of itself
        backend="heuristic",
        breakdown={"novelty_prior": prior, "tight_ratio": round(tight_ratio, 3),
                   "support": round(support, 3)},
    )


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def promise_graph(cand: dict) -> Promise:
    """Promise score for one graph-inequality candidate dict.

    Uses Jev when configured and reachable; otherwise the heuristic fallback.
    """
    if configured():
        p = _jev_call(_candidate_state(cand))
        if p is not None:
            return p
    return _heuristic(cand)


def rerank(candidates: list[dict]) -> list[dict]:
    """Attach a ``promise`` (and ``promise_backend``) to each candidate and sort.

    Ordering only: keeps the candidate/derived/known tiers (an unexplained bound
    still comes before an explained one), then orders *within* a tier by promise,
    breaking ties by tightness. Returns new dicts; never mutates truth fields.
    """
    scored = []
    for c in candidates:
        p = promise_graph(c)
        scored.append({**c, "promise": round(p.value, 4),
                       "promise_backend": p.backend})
    scored.sort(key=lambda d: (_NOVELTY_RANK.get(d.get("novelty"), 1),
                               -d.get("promise", 0.0), -d.get("tight_on", 0)))
    return scored
