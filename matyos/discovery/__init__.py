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

__all__ = [
    "MathObject",
    "Sequence",
    "Formula",
    "Series",
    "DiscoveryEngine",
    "Candidate",
]
