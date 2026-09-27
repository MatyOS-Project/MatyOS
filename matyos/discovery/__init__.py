"""MatyOS v2 — the mathematical discovery engine.

This package is a *scaffold*, not a finished discovery system. Its purpose is to
lay out the four-component architecture from ``docs/discovery-v2.md`` with real,
runnable interfaces and one honest end-to-end toy loop, so the pieces that matter
(cross-domain transfer, computable interestingness) have somewhere to grow.

Components:

- :mod:`matyos.discovery.objects`    — Object Representation Layer
- :mod:`matyos.discovery.generator`  — Generator / Mutator (incl. cross-domain transfer)
- :mod:`matyos.discovery.scorer`     — Interestingness Scorer (computable proxies)
- :mod:`matyos.discovery.verify`     — Cheap verification (numeric confirm, prior-art)
- :mod:`matyos.discovery.triage`     — ranked shortlist for a human
- :mod:`matyos.discovery.engine`     — the discovery loop that ties them together

Anything marked ``STUB`` is a deliberate placeholder with a stable signature and
no real implementation yet. Nothing here should be mistaken for working discovery.
"""

from matyos.discovery.objects import MathObject, Sequence, Formula, Series
from matyos.discovery.engine import DiscoveryEngine, Candidate
from matyos.discovery import jev, stoqos
from matyos.discovery.stoqos import judge, realistic_score, score_evidence, Judgement

__all__ = [
    "MathObject",
    "Sequence",
    "Formula",
    "Series",
    "DiscoveryEngine",
    "Candidate",
    # scorers for the REALISTIC level (see docs/stoqos.md)
    "jev",              # Jev-backed promise scorer for ranking candidates
    "stoqos",           # calibrated REALISTIC-level model (Stoqos)
    "judge",            # typed verdict for one claim (realistic/uncertain/false/unknown)
    "realistic_score",  # calibrated P(true) for a graph-inequality bound
    "score_evidence",   # domain-general REALISTIC score from evidence alone
    "Judgement",
]
