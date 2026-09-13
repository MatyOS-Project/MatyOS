"""Human triage — turn scored, verified candidates into a short ranked report.

The system is deliberately not autonomous. Its output is a shortlist for a human to
judge, ordered by interestingness, with the reason for each ranking made explicit
so the human can disagree quickly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from matyos.discovery.engine import Candidate


def render_shortlist(candidates: list["Candidate"], limit: int = 10) -> str:
    ranked = sorted(candidates, key=lambda c: c.score.total, reverse=True)[:limit]
    lines: list[str] = []
    lines.append("=" * 66)
    lines.append(" MatyOS v2 — discovery shortlist (for human triage)")
    lines.append("=" * 66)
    if not ranked:
        lines.append(" (no candidates)")
        return "\n".join(lines)

    for i, c in enumerate(ranked, 1):
        label = _describe(c)
        lines.append(f"\n[{i}] score {c.score.total:.3f}   {label}")
        lines.append(f"     provenance: {c.object.provenance}")
        parts = "  ".join(f"{k}={v:.2f}" for k, v in c.score.breakdown.items())
        lines.append(f"     proxies:    {parts}")
        for note in c.score.notes.values():
            lines.append(f"     note:       {note}")
        if c.verification.prior_art:
            lines.append(f"     KNOWN:      {c.verification.prior_art}")
        elif c.verification.confirmed:
            lines.append("     status:     confirmed, no prior art in local table — worth a look")
        for vn in c.verification.notes:
            lines.append(f"     verify:     {vn}")
    lines.append("\n" + "-" * 66)
    lines.append(" Ranking is a triage aid, not a judgement. A human decides.")
    lines.append("-" * 66)
    return "\n".join(lines)


def _describe(c: "Candidate") -> str:
    from matyos.discovery.objects import Sequence, Formula
    obj = c.object
    if isinstance(obj, Formula):
        return f"formula: {obj.text}"
    if isinstance(obj, Sequence):
        head = ", ".join(str(t) for t in obj.terms[:8])
        return f"sequence: {head}{' ...' if len(obj.terms) > 8 else ''}"
    return obj.key()
