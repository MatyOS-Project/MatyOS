"""
Sound propositional proof checker for El.

Milestone 1 of the proof-assistant direction: instead of "assume a complete
proof is valid", we actually decide propositional validity by truth tables.

A proposition is verified by checking that it is entailed by its premises
(axioms + hypotheses) under *every* truth assignment to its atoms. This is
decidable, finite, and trivially sound for classical propositional logic.

The `realistic` value (El's third truth value) is detected and reported as
UNCERTAIN rather than silently coerced -- it is the seam where three-valued
logic will plug in later (Milestone 1b).
"""

from utils.constants import TRUE, FALSE, REALISTIC
from utils.data_classes import (
    PropAtom, PropConst, PropNot, PropAnd, PropOr, PropImplies, PropIff,
)

# Verdict constants
PROVEN = "PROVEN"
DISPROVEN = "DISPROVEN"
UNCERTAIN = "UNCERTAIN"

_BIN = (PropAnd, PropOr, PropImplies, PropIff)


def collect_atoms(node, acc=None):
    """Return the set of propositional-variable names occurring in node."""
    if acc is None:
        acc = set()
    if isinstance(node, PropAtom):
        acc.add(node.name)
    elif isinstance(node, PropNot):
        collect_atoms(node.operand, acc)
    elif isinstance(node, _BIN):
        collect_atoms(node.left, acc)
        collect_atoms(node.right, acc)
    # PropConst contributes no atoms
    return acc


def contains_realistic(node):
    """True if the proposition mentions the `realistic` (uncertain) value."""
    if isinstance(node, PropConst):
        return node.value == REALISTIC
    if isinstance(node, PropAtom):
        return False
    if isinstance(node, PropNot):
        return contains_realistic(node.operand)
    if isinstance(node, _BIN):
        return contains_realistic(node.left) or contains_realistic(node.right)
    return False


def eval_prop(node, assignment):
    """Evaluate a (realistic-free) proposition under a boolean assignment."""
    if isinstance(node, PropConst):
        return node.value == TRUE
    if isinstance(node, PropAtom):
        return assignment[node.name]
    if isinstance(node, PropNot):
        return not eval_prop(node.operand, assignment)
    if isinstance(node, PropAnd):
        return eval_prop(node.left, assignment) and eval_prop(node.right, assignment)
    if isinstance(node, PropOr):
        return eval_prop(node.left, assignment) or eval_prop(node.right, assignment)
    if isinstance(node, PropImplies):
        return (not eval_prop(node.left, assignment)) or eval_prop(node.right, assignment)
    if isinstance(node, PropIff):
        return eval_prop(node.left, assignment) == eval_prop(node.right, assignment)
    raise TypeError("not a proposition node: {}".format(type(node).__name__))


def all_assignments(atoms):
    """Yield every boolean assignment over the given atom names."""
    atoms = sorted(atoms)
    n = len(atoms)
    for i in range(2 ** n):
        yield {atom: bool((i >> j) & 1) for j, atom in enumerate(atoms)}


def check_entailment(premises, goal):
    """
    Decide whether `goal` is entailed by `premises`.

    Returns (verdict, counterexample) where verdict is one of
    PROVEN / DISPROVEN / UNCERTAIN. The counterexample (a falsifying
    assignment) is provided only for DISPROVEN, else None.

    With no premises this reduces to "is goal a tautology?".
    """
    premises = list(premises or [])
    if contains_realistic(goal) or any(contains_realistic(p) for p in premises):
        return UNCERTAIN, None

    atoms = set()
    for p in premises:
        collect_atoms(p, atoms)
    collect_atoms(goal, atoms)

    for assignment in all_assignments(atoms):
        if all(eval_prop(p, assignment) for p in premises):
            if not eval_prop(goal, assignment):
                return DISPROVEN, assignment
    return PROVEN, None


def prop_to_str(node):
    """Human-readable rendering of a proposition (also via node.__str__)."""
    return str(node)


def format_counterexample(assignment):
    """Render a falsifying assignment as 'P=true, Q=false'."""
    if not assignment:
        return "(no atoms)"
    return ", ".join(
        "{}={}".format(name, "true" if val else "false")
        for name, val in sorted(assignment.items())
    )
