"""Epistemic labelling of a discovery, in MatyOS's three-valued `realistic` logic.

A discovered closed form is not a theorem. This maps the evidence to the same
truth values the kernel's epistemic layer uses — TRUE (certified by proof),
REALISTIC (trusted for argument but unproven), FALSE (refuted) — so a find never
masquerades as a fact. Novelty (known vs new) is tracked separately: it is about
prior art, not truth.
"""

from __future__ import annotations

from matyos.logic import realistic


def realistic_label(*, has_closed_form: bool, refutation: str,
                    prior_art: str | None, proven: bool = False,
                    is_mystery: bool = False) -> dict:
    """Return {truth, truth_name, status, novelty} for a candidate.

    truth uses matyos.logic.realistic's constants (TRUE / REALISTIC / FALSE).
    - refuted            -> FALSE
    - proven (kernel/Lean) -> TRUE     (not reachable from numeric discovery yet)
    - mystery            -> REALISTIC  (a real, stable constant we cannot name)
    - otherwise          -> REALISTIC (found, survived tests, but unproven)
    """
    if is_mystery and not has_closed_form:
        return {"truth": realistic.REALISTIC,
                "truth_name": realistic.name_of(realistic._FROM_CONST[realistic.REALISTIC]),
                "status": "mystery — stable constant, no known closed form",
                "novelty": "unknown"}
    if not has_closed_form:
        return {"truth": None, "truth_name": None,
                "status": "no closed form", "novelty": None}
    if refutation == "refuted":
        truth, status = realistic.FALSE, "refuted"
    elif proven:
        truth, status = realistic.TRUE, "certified (proven)"
    else:
        truth, status = realistic.REALISTIC, "realistic (unproven, survived tests)"
    return {
        "truth": truth,
        "truth_name": realistic.name_of(realistic._FROM_CONST[truth]),
        "status": status,
        "novelty": "known" if prior_art else "novel",
    }
