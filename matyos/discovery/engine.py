"""The discovery loop.

Ties the four components into one pass:

    seeds → generate (mutate + cross-domain transfer) → score → verify → shortlist

This is a single-generation loop by design — enough to demonstrate the architecture
end to end. A real engine iterates: feed the surviving candidates back in as seeds,
under a budget, the way FunSearch/AlphaEvolve run an evolutionary search. That loop
is future work; the seam for it is :meth:`DiscoveryEngine.step`.
"""

from __future__ import annotations

from dataclasses import dataclass

from matyos.discovery.objects import MathObject
from matyos.discovery import generator, scorer, verify as verify_mod, triage
from matyos.discovery.scorer import Score
from matyos.discovery.verify import Verification


@dataclass(frozen=True)
class Candidate:
    object: MathObject
    score: Score
    verification: Verification


class DiscoveryEngine:
    """A minimal, single-generation discovery engine.

    ``min_score`` filters out candidates the scorer found uninteresting before they
    reach verification, keeping the shortlist cheap.
    """

    def __init__(self, min_score: float = 0.2) -> None:
        self.min_score = min_score

    def step(self, seeds: list[MathObject]) -> list[MathObject]:
        """One generation of candidate production from ``seeds`` (no scoring).

        Includes the seeds themselves plus every mutation and cross-domain transfer,
        deduplicated by object key.
        """
        produced: dict[str, MathObject] = {}
        for seed in seeds:
            produced.setdefault(seed.key(), seed)
            for m in generator.mutate(seed):
                produced.setdefault(m.key(), m)
            for t in generator.cross_domain_transfer(seed):
                produced.setdefault(t.key(), t)
        return list(produced.values())

    def run(self, seeds: list[MathObject]) -> list[Candidate]:
        """Full pass: produce, score, filter, verify. Returns scored candidates."""
        candidates: list[Candidate] = []
        for obj in self.step(seeds):
            s = scorer.score(obj)
            if s.total < self.min_score:
                continue
            v = verify_mod.verify(obj)
            candidates.append(Candidate(object=obj, score=s, verification=v))
        return candidates

    def report(self, seeds: list[MathObject], limit: int = 10) -> str:
        return triage.render_shortlist(self.run(seeds), limit=limit)

    def records(self, seeds: list[MathObject], limit: int = 20) -> list[dict]:
        """Structured results for a UI / tooling — the JSON form of the shortlist."""
        ranked = sorted(self.run(seeds), key=lambda c: c.score.total, reverse=True)[:limit]
        return [_candidate_record(c, i + 1) for i, c in enumerate(ranked)]


def _candidate_record(c: Candidate, rank: int) -> dict:
    from matyos.discovery.objects import Sequence, Formula
    obj = c.object
    if isinstance(obj, Formula):
        display = {"kind": "formula", "text": obj.text}
    elif isinstance(obj, Sequence):
        display = {"kind": "sequence", "terms": [str(t) for t in obj.terms[:12]]}
    else:
        display = {"kind": "object", "text": obj.key()}
    return {
        "rank": rank,
        "display": display,
        "provenance": obj.provenance,
        "score": round(c.score.total, 4),
        "proxies": {k: round(v, 3) for k, v in c.score.breakdown.items()},
        "closed_form": c.score.notes.get("numerical_anomaly", ""),
        "verification": {
            "confirmed": c.verification.confirmed,
            "prior_art": c.verification.prior_art,
            "notes": c.verification.notes,
        },
    }
