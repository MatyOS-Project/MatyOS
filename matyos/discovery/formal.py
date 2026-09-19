"""A `Conjecture`: a discovery, its formal Lean statement, and its proof status —
bundled as one object.

MatyOS discovers an object (a sequence limit, a graph inequality, …) and, when it
has a closed form, can state it formally in Lean. Those had lived apart — a numeric
record here, a Lean string there. `Conjecture` unifies them: the discovered object,
the human-readable claim, the Lean 4 statement (with `sorry`), the honest
`realistic` label, and — once attempted — the proof result from `lean.try_prove`.
This is the substrate the hard-problems workspace builds on: to *hold* a claim is
to hold its statement and its proof status in one place.

Honesty is preserved: `proved` is true only when Lean accepted a proof; a
conjecture with no formal statement (or that Lean could not close) never reads as
proved.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from matyos.discovery.objects import MathObject


@dataclass(frozen=True)
class Conjecture:
    claim: str                              # human-readable statement / closed form
    lean_statement: str | None = None       # formal Lean 4 statement (with `sorry`)
    label: dict = field(default_factory=dict)   # realistic label (truth/status/novelty)
    proof: dict | None = None                # result of lean.try_prove, or None
    source: str = "discovery"                # "discovery" | "famous-problem" | ...
    object: MathObject | None = None         # the discovered object, when there is one

    @property
    def proved(self) -> bool:
        """True only if a Lean proof was accepted — never on evidence alone."""
        return bool(self.proof and self.proof.get("proved"))

    @property
    def status(self) -> str:
        """One honest word: proved / open / stated / refuted."""
        if self.proved:
            return "proved"
        if self.label.get("truth_name") == "FALSE" or self.label.get("refutation"):
            return "refuted"
        if self.lean_statement is None:
            return "stated"          # nothing formal to attempt
        return "open"                # has a statement, not (yet) proved

    def attempt_proof(self, timeout: int = 120) -> "Conjecture":
        """Return a copy with a proof attempt attached (via `lean.try_prove`).

        A conjecture with no `lean_statement` is returned unchanged. Never fabricates
        a proof — only records what Lean returned.
        """
        if not self.lean_statement:
            return self
        from matyos.discovery import lean
        return replace(self, proof=lean.try_prove(self.lean_statement, timeout=timeout))

    def to_dict(self) -> dict:
        return {
            "claim": self.claim,
            "lean_statement": self.lean_statement,
            "label": self.label,
            "proof": self.proof,
            "proved": self.proved,
            "status": self.status,
            "source": self.source,
            "object": self.object.key() if self.object is not None else None,
        }

    @staticmethod
    def from_record(record: dict, object: MathObject | None = None) -> "Conjecture":
        """Build a Conjecture from an engine candidate record (see engine._candidate_record)."""
        claim = record.get("closed_form") or record.get("display", {}).get("text", "") \
            or record.get("display", {}).get("kind", "object")
        return Conjecture(
            claim=claim,
            lean_statement=record.get("lean_statement"),
            label=record.get("label", {}),
            source="discovery",
            object=object,
        )
