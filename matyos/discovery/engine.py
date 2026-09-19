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
                # chain one more hop, e.g. sequence -> formula -> series
                for t2 in generator.cross_domain_transfer(t):
                    produced.setdefault(t2.key(), t2)
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

    def conjectures(self, seeds: list[MathObject], limit: int = 20,
                    prove: bool = False, timeout: int = 120) -> list:
        """Discoveries as first-class `Conjecture` objects (claim + Lean statement +
        proof status in one place). With ``prove=True`` each conjecture that carries
        a Lean statement is run through ``lean.try_prove`` and the result attached —
        honest: only Lean-accepted proofs count as proved."""
        from matyos.discovery.formal import Conjecture
        ranked = sorted(self.run(seeds), key=lambda c: c.score.total, reverse=True)[:limit]
        out = []
        for i, c in enumerate(ranked):
            conj = Conjecture.from_record(_candidate_record(c, i + 1), object=c.object)
            out.append(conj.attempt_proof(timeout=timeout) if prove else conj)
        return out

    def loop(self, seeds: list[MathObject], rounds: int = 3, breadth: int = 12,
             store=None, reasoner=None) -> dict:
        """Iterated discovery: run, remember, let a reasoner propose the next seeds.

        Each round scores the current frontier, records every new candidate in
        memory (deduplicated), then asks ``reasoner`` what to try next given the
        state so far, dropping anything already seen. The default reasoner mutates
        the current seeds (no model); pass a CallbackReasoner to let Claude or any
        LLM drive the search instead. Stops after ``rounds`` or when the reasoner
        proposes nothing new.
        """
        from matyos.discovery.store import CandidateStore
        from matyos.discovery.objects import Sequence
        from matyos.discovery.reasoner import MutationReasoner
        store = store or CandidateStore()
        reasoner = reasoner or MutationReasoner()
        frontier = list(seeds)
        seen_seeds: set[str] = set()
        rounds_run = 0
        for r in range(rounds):
            frontier = [s for s in frontier if s.key() not in seen_seeds]
            if not frontier:
                break
            rounds_run += 1
            for s in frontier:
                seen_seeds.add(s.key())
            for c in self.run(frontier):
                rec = _candidate_record(c, 0)
                rec["round"] = r
                store.add(c.object.key(), rec)
            context = self._reasoner_context(frontier, store)
            proposals = reasoner.propose(context)
            nxt: list[MathObject] = []
            for seq in proposals:
                s = Sequence.of(seq)
                if s.key() not in seen_seeds:
                    nxt.append(s)
            frontier = nxt[:breadth]
        ranked = sorted(store.all(), key=lambda r: r["score"], reverse=True)
        for i, rec in enumerate(ranked, 1):
            rec["rank"] = i
        return {"rounds_run": rounds_run, "unique": len(store), "candidates": ranked}

    @staticmethod
    def _reasoner_context(frontier, store) -> dict:
        """The search state handed to a reasoner: current seeds, closed forms
        found, and mystery constants — enough for a model to decide where to dig."""
        from matyos.discovery.objects import Sequence
        seqs = [[int(t) for t in s.terms] for s in frontier
                if isinstance(s, Sequence) and all(t.denominator == 1 for t in s.terms)]
        found, myst = [], []
        for rec in store.all():
            cf = rec.get("closed_form", "")
            if "(PSLQ):" in cf:
                found.append(cf.split("(PSLQ):", 1)[1].strip())
            elif (rec.get("label") or {}).get("status", "").startswith("mystery"):
                myst.append(rec["display"].get("text", "?"))
        return {"frontier": seqs, "found": found, "mysteries": myst}


def _candidate_record(c: Candidate, rank: int) -> dict:
    from matyos.discovery.objects import Sequence, Formula
    obj = c.object
    if isinstance(obj, Formula):
        display = {"kind": "formula", "text": obj.text}
    elif isinstance(obj, Sequence):
        display = {"kind": "sequence", "terms": [str(t) for t in obj.terms[:12]]}
    else:
        display = {"kind": "object", "text": obj.key()}
    from matyos.discovery import lean
    record = {
        "rank": rank,
        "display": display,
        "provenance": obj.provenance,
        "score": round(c.score.total, 4),
        "proxies": {k: round(v, 3) for k, v in c.score.breakdown.items()},
        "closed_form": c.score.notes.get("numerical_anomaly", ""),
        "verification": {
            "confirmed": c.verification.confirmed,
            "prior_art": c.verification.prior_art,
            "refutation": c.verification.refutation,
            "notes": c.verification.notes,
        },
        "label": c.verification.label,
    }
    record["lean_statement"] = lean.lean_statement(record)
    return record
