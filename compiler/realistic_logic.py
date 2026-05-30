"""
The `realistic` value, done rigorously: three-valued propositional logic.

El's distinctive idea is a third truth value, `realistic` (U), alongside
`true` (T) and `false` (F). The original code treated it ad hoc (and even
raised on `and`/`or`). This module gives it a precise, textbook semantics so it
becomes a real logic instead of a slogan.

Two classical 3-valued systems are provided; they agree everywhere EXCEPT
implication (and hence the biconditional):

  * Kleene strong logic (K3): U is "no information". P -> P is NOT valid
    (U -> U = U), modelling genuine ignorance.
  * Lukasiewicz (L3): U is "half true". P -> P IS valid (U -> U = T),
    modelling a degree of truth.

Truth order: F < U < T.  `and` = min, `or` = max, `not` flips T/F and fixes U.

Designated value = {T}. A proposition is VALID iff it evaluates to T under
EVERY assignment of {T,F,U} to its atoms; premises ENTAIL a goal iff every
assignment making all premises T also makes the goal T.

Landmark consequences (these are the *point* of the third value):
  * Excluded middle  P \\/ ~P  is NOT valid (U \\/ U = U).
  * Non-contradiction ~(P /\\ ~P) is NOT valid (= U at P=U).
These failures are correct: a `realistic` proposition is neither affirmed nor
denied, so the classical "every proposition is true-or-false" laws lapse.

IMPORTANT design boundary: this is reasoning *about* uncertain propositions.
It must stay OUTSIDE the trusted dependent-type kernel (`kernel/core.py`),
which remains classical/constructive and sound. `realistic` is an epistemic
layer above the kernel (see ROADMAP.md, "Realistic track"), never a third
value smuggled into the trusted core.
"""

from itertools import product
from utils.constants import TRUE, FALSE, REALISTIC
from utils.data_classes import (
    PropAtom, PropConst, PropNot, PropAnd, PropOr, PropImplies, PropIff,
)

# Truth values as an order F < U < T (so AND=min, OR=max).
F, U, T = 0, 1, 2
_NAMES = {F: "false", U: "realistic", T: "true"}
_FROM_CONST = {FALSE: F, REALISTIC: U, TRUE: T}

KLEENE = "kleene"
LUKASIEWICZ = "lukasiewicz"

_BIN = (PropAnd, PropOr, PropImplies, PropIff)


def name_of(v):
    return _NAMES[v]


def _neg(v):
    return T - v  # F<->T, U fixed


def _impl(p, q, semantics):
    if semantics == KLEENE:
        return max(_neg(p), q)            # ~P \/ Q
    if semantics == LUKASIEWICZ:
        # min(1, 1 - p + q) on the scale F=0,U=0.5,T=1, then mapped back
        val = min(2, 2 - p + q)           # works on the {0,1,2} scale
        return val
    raise ValueError(f"unknown semantics: {semantics}")


def evaluate(node, assignment, semantics=KLEENE):
    """Evaluate a proposition to T/U/F under a 3-valued assignment."""
    if isinstance(node, PropConst):
        return _FROM_CONST[node.value]
    if isinstance(node, PropAtom):
        return assignment[node.name]
    if isinstance(node, PropNot):
        return _neg(evaluate(node.operand, assignment, semantics))
    if isinstance(node, PropAnd):
        return min(evaluate(node.left, assignment, semantics),
                   evaluate(node.right, assignment, semantics))
    if isinstance(node, PropOr):
        return max(evaluate(node.left, assignment, semantics),
                   evaluate(node.right, assignment, semantics))
    if isinstance(node, PropImplies):
        return _impl(evaluate(node.left, assignment, semantics),
                     evaluate(node.right, assignment, semantics), semantics)
    if isinstance(node, PropIff):
        p = evaluate(node.left, assignment, semantics)
        q = evaluate(node.right, assignment, semantics)
        return min(_impl(p, q, semantics), _impl(q, p, semantics))
    raise TypeError(f"not a proposition: {type(node).__name__}")


def atoms_of(node, acc=None):
    if acc is None:
        acc = set()
    if isinstance(node, PropAtom):
        acc.add(node.name)
    elif isinstance(node, PropNot):
        atoms_of(node.operand, acc)
    elif isinstance(node, _BIN):
        atoms_of(node.left, acc)
        atoms_of(node.right, acc)
    return acc


def _assignments(atoms):
    atoms = sorted(atoms)
    for combo in product((F, U, T), repeat=len(atoms)):
        yield dict(zip(atoms, combo))


def is_valid(goal, semantics=KLEENE):
    """True iff goal is designated (=T) under every 3-valued assignment.

    Returns (valid: bool, counterexample: dict|None) where the counterexample
    is the first assignment under which goal is not T.
    """
    for asg in _assignments(atoms_of(goal)):
        if evaluate(goal, asg, semantics) != T:
            return False, asg
    return True, None


def entails(premises, goal, semantics=KLEENE):
    """Premises designate -> goal designates, under every 3-valued assignment."""
    premises = list(premises or [])
    atoms = set()
    for p in premises:
        atoms_of(p, atoms)
    atoms_of(goal, atoms)
    for asg in _assignments(atoms):
        if all(evaluate(p, asg, semantics) == T for p in premises):
            if evaluate(goal, asg, semantics) != T:
                return False, asg
    return True, None


def truth_table(node, semantics=KLEENE):
    """Return (atom_names, rows) where each row is (assignment, value)."""
    names = sorted(atoms_of(node))
    rows = []
    for asg in _assignments(names):
        rows.append((asg, evaluate(node, asg, semantics)))
    return names, rows


# --------------------------------------------------------------------------
# Self-test / demonstration.
# --------------------------------------------------------------------------
if __name__ == "__main__":
    def atom(n):
        return PropAtom(n)

    P, Q = atom("P"), atom("Q")
    excluded_middle = PropOr(P, PropNot(P))
    non_contradiction = PropNot(PropAnd(P, PropNot(P)))
    self_implies = PropImplies(P, P)
    modus_ponens = PropImplies(PropAnd(PropImplies(P, Q), P), Q)

    cases = [
        ("excluded middle  P \\/ ~P", excluded_middle),
        ("non-contradiction ~(P /\\ ~P)", non_contradiction),
        ("self-implication  P -> P", self_implies),
        ("modus ponens  (P->Q)/\\P -> Q", modus_ponens),
    ]

    for sem in (KLEENE, LUKASIEWICZ):
        print(f"\n================  {sem.upper()}  ================")
        for label, prop in cases:
            valid, cx = is_valid(prop, sem)
            verdict = "VALID" if valid else "not valid"
            extra = "" if valid else \
                f"  (e.g. {', '.join(f'{k}={name_of(v)}' for k, v in cx.items())} -> {name_of(evaluate(prop, cx, sem))})"
            print(f"   {label:32s} : {verdict}{extra}")

    print("\nKleene truth table for  P -> P :")
    names, rows = truth_table(self_implies, KLEENE)
    for asg, val in rows:
        binding = ", ".join(f"{k}={name_of(v)}" for k, v in asg.items())
        print(f"   {binding:14s} => {name_of(val)}")
