"""Rigorous tests for the three-valued ("realistic") propositional logic engine.

Truth order: F(0) < U(1) < T(2).  AND = min, OR = max, NOT flips T/F and fixes U.
Designated value = {T}: a formula is VALID iff it evaluates to T under EVERY
assignment of {T,U,F} to its atoms.

The two semantics agree everywhere except implication (and hence iff):
  * Kleene (K3):       P -> Q = max(~P, Q)          => U -> U = U
  * Lukasiewicz (L3):  P -> Q = min(2, 2 - P + Q)   => U -> U = T

Every expected value below was derived by reasoning about the semantics and
then confirmed by running the module.
"""

import pytest

from matyos.logic.realistic import (
    F, U, T,
    TRUE, FALSE, REALISTIC,
    KLEENE, LUKASIEWICZ,
    PropAtom, PropConst, PropNot, PropAnd, PropOr, PropImplies, PropIff,
    evaluate, atoms_of, is_valid, entails, truth_table, name_of,
)


# --------------------------------------------------------------------------
# Fixtures / shorthands
# --------------------------------------------------------------------------
P = PropAtom("P")
Q = PropAtom("Q")
BOTH = (KLEENE, LUKASIEWICZ)


def asg(**kw):
    return dict(kw)


# --------------------------------------------------------------------------
# Truth-value constants and naming
# --------------------------------------------------------------------------
def test_truth_value_ints_and_order():
    assert (F, U, T) == (0, 1, 2)
    assert F < U < T


def test_name_of():
    assert name_of(F) == "false"
    assert name_of(U) == "realistic"
    assert name_of(T) == "true"


def test_const_mapping():
    # PropConst maps the string constants back onto the {0,1,2} scale.
    assert evaluate(PropConst(TRUE), {}) == T
    assert evaluate(PropConst(FALSE), {}) == F
    assert evaluate(PropConst(REALISTIC), {}) == U


# --------------------------------------------------------------------------
# NOT = flip (T<->F, U fixed)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("v,expected", [(F, T), (U, U), (T, F)])
@pytest.mark.parametrize("sem", BOTH)
def test_not_table(v, expected, sem):
    assert evaluate(PropNot(P), asg(P=v), sem) == expected


# --------------------------------------------------------------------------
# AND = min,  OR = max  (semantics-independent)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("sem", BOTH)
def test_and_is_min(sem):
    assert evaluate(PropAnd(P, Q), asg(P=U, Q=T), sem) == U   # min(U,T)=U
    assert evaluate(PropAnd(P, Q), asg(P=U, Q=F), sem) == F   # min(U,F)=F
    assert evaluate(PropAnd(P, Q), asg(P=T, Q=T), sem) == T


@pytest.mark.parametrize("sem", BOTH)
def test_and_false_is_absorbing(sem):
    # F /\ anything = F, regardless of the other operand.
    for other in (F, U, T):
        assert evaluate(PropAnd(P, Q), asg(P=F, Q=other), sem) == F
        assert evaluate(PropAnd(P, Q), asg(P=other, Q=F), sem) == F


@pytest.mark.parametrize("sem", BOTH)
def test_or_is_max(sem):
    assert evaluate(PropOr(P, Q), asg(P=U, Q=F), sem) == U   # max(U,F)=U
    assert evaluate(PropOr(P, Q), asg(P=U, Q=T), sem) == T   # max(U,T)=T
    assert evaluate(PropOr(P, Q), asg(P=F, Q=F), sem) == F


@pytest.mark.parametrize("sem", BOTH)
def test_or_true_is_absorbing(sem):
    # T \/ anything = T, regardless of the other operand.
    for other in (F, U, T):
        assert evaluate(PropOr(P, Q), asg(P=T, Q=other), sem) == T
        assert evaluate(PropOr(P, Q), asg(P=other, Q=T), sem) == T


# --------------------------------------------------------------------------
# Implication: the ONLY place the two semantics diverge.
# --------------------------------------------------------------------------
def test_implication_diverges_on_U_to_U():
    # Kleene: U -> U = max(~U, U) = max(U, U) = U.
    assert evaluate(PropImplies(P, Q), asg(P=U, Q=U), KLEENE) == U
    # Lukasiewicz: U -> U = min(2, 2 - 1 + 1) = 2 = T.
    assert evaluate(PropImplies(P, Q), asg(P=U, Q=U), LUKASIEWICZ) == T


@pytest.mark.parametrize("sem", BOTH)
def test_implication_agreements(sem):
    # T -> F = F in both (K: max(~T,F)=max(F,F)=F; L: min(2,2-2+0)=0).
    assert evaluate(PropImplies(P, Q), asg(P=T, Q=F), sem) == F
    # F -> U = T in both (K: max(~F,U)=max(T,U)=T; L: min(2,2-0+1)=2=T).
    assert evaluate(PropImplies(P, Q), asg(P=F, Q=U), sem) == T


@pytest.mark.parametrize("sem", BOTH)
def test_implication_other_agreeing_cells(sem):
    # U -> T = T in both; T -> U = U in both.
    assert evaluate(PropImplies(P, Q), asg(P=U, Q=T), sem) == T
    assert evaluate(PropImplies(P, Q), asg(P=T, Q=U), sem) == U


# --------------------------------------------------------------------------
# Biconditional follows implication: it also diverges at U<->U.
# --------------------------------------------------------------------------
def test_iff_diverges_on_U():
    # iff = min(P->Q, Q->P). At P=Q=U: K gives min(U,U)=U; L gives min(T,T)=T.
    assert evaluate(PropIff(P, Q), asg(P=U, Q=U), KLEENE) == U
    assert evaluate(PropIff(P, Q), asg(P=U, Q=U), LUKASIEWICZ) == T


# --------------------------------------------------------------------------
# Landmark validity results (the whole point of the third value).
# --------------------------------------------------------------------------
@pytest.mark.parametrize("sem", BOTH)
def test_excluded_middle_not_valid(sem):
    # P \/ ~P : at P=U gives max(U,U)=U != T. Fails in BOTH semantics.
    valid, cx = is_valid(PropOr(P, PropNot(P)), sem)
    assert valid is False
    assert cx == {"P": U}


@pytest.mark.parametrize("sem", BOTH)
def test_non_contradiction_not_valid(sem):
    # ~(P /\ ~P): at P=U gives ~min(U,U)=~U=U != T. Fails in BOTH semantics.
    valid, cx = is_valid(PropNot(PropAnd(P, PropNot(P))), sem)
    assert valid is False
    assert cx == {"P": U}


def test_self_implication_kleene_not_valid():
    # P -> P in Kleene: at P=U, U -> U = U != T. NOT valid (genuine ignorance).
    valid, cx = is_valid(PropImplies(P, P), KLEENE)
    assert valid is False
    assert cx == {"P": U}


def test_self_implication_lukasiewicz_valid():
    # P -> P in Lukasiewicz: U -> U = T, so it is T everywhere => VALID.
    valid, cx = is_valid(PropImplies(P, P), LUKASIEWICZ)
    assert valid is True
    assert cx is None


@pytest.mark.parametrize("sem", BOTH)
def test_modus_ponens_schema_not_valid(sem):
    # ((P->Q) /\ P) -> Q : at P=U, Q=F the antecedent is U and consequent F,
    # so U -> F = F != T in both semantics. NOT valid as a formula.
    schema = PropImplies(PropAnd(PropImplies(P, Q), P), Q)
    valid, cx = is_valid(schema, sem)
    assert valid is False
    assert cx == {"P": U, "Q": F}


# --------------------------------------------------------------------------
# A genuinely valid formula must be reachable (is_valid can return True).
# --------------------------------------------------------------------------
@pytest.mark.parametrize("sem", BOTH)
def test_const_true_is_valid(sem):
    valid, cx = is_valid(PropConst(TRUE), sem)
    assert valid is True
    assert cx is None


@pytest.mark.parametrize("sem", BOTH)
def test_const_false_not_valid(sem):
    # No atoms => exactly one (empty) assignment; the counterexample is {}.
    valid, cx = is_valid(PropConst(FALSE), sem)
    assert valid is False
    assert cx == {}


@pytest.mark.parametrize("sem", BOTH)
def test_or_with_true_constant_is_valid(sem):
    # P \/ TRUE = max(P, T) = T for every P => VALID in both semantics.
    valid, cx = is_valid(PropOr(P, PropConst(TRUE)), sem)
    assert valid is True
    assert cx is None


# --------------------------------------------------------------------------
# Entailment.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("sem", BOTH)
def test_modus_ponens_entailment_holds(sem):
    # {P, P->Q} |= Q.  Reasoning: entailment only inspects assignments where
    # ALL premises are designated (=T). P=T forces the live cases, and
    # P->Q = T with P=T forces Q=T (T->Q=T only when Q=T in both semantics).
    # So in every premise-satisfying world Q is T. Entailment HOLDS.
    ok, cx = entails([P, PropImplies(P, Q)], Q, sem)
    assert ok is True
    assert cx is None


@pytest.mark.parametrize("sem", BOTH)
def test_unsatisfiable_premises_entail_anything(sem):
    # PropConst(FALSE) is never designated, so the "all premises T" guard is
    # never satisfied => entailment is vacuously true for any goal.
    ok, cx = entails([PropConst(FALSE)], Q, sem)
    assert ok is True
    assert cx is None


@pytest.mark.parametrize("sem", BOTH)
def test_entailment_can_fail(sem):
    # {P} |= Q is false: P=T, Q=F satisfies the premise but not the goal.
    ok, cx = entails([P], Q, sem)
    assert ok is False
    assert evaluate(P, cx, sem) == T
    assert evaluate(Q, cx, sem) != T


def test_empty_premises_reduce_to_validity():
    # With no premises, every assignment "satisfies" the (empty) premise set,
    # so entailment of G reduces to validity of G.
    assert entails([], PropConst(TRUE), KLEENE) == (True, None)
    ok, _ = entails([], PropImplies(P, P), KLEENE)
    assert ok is False  # mirrors P->P not being valid in Kleene


# --------------------------------------------------------------------------
# atoms_of and truth_table shapes.
# --------------------------------------------------------------------------
def test_atoms_of():
    assert atoms_of(PropImplies(P, Q)) == {"P", "Q"}
    assert atoms_of(PropConst(TRUE)) == set()
    assert atoms_of(PropNot(PropAnd(P, PropNot(P)))) == {"P"}
    # Repeated atoms collapse to the set.
    assert atoms_of(PropAnd(P, P)) == {"P"}


@pytest.mark.parametrize("sem", BOTH)
@pytest.mark.parametrize("node,n_atoms", [
    (PropConst(TRUE), 0),
    (PropNot(P), 1),
    (PropImplies(P, Q), 2),
])
def test_truth_table_row_count(node, n_atoms, sem):
    names, rows = truth_table(node, sem)
    assert names == sorted(atoms_of(node))
    # Row count is 3 ** (number of atoms): three-valued, full enumeration.
    assert len(rows) == 3 ** n_atoms
    # Every row is (assignment-dict, value-in-{F,U,T}).
    for binding, val in rows:
        assert set(binding) == set(names)
        assert val in (F, U, T)


def test_truth_table_values_match_evaluate():
    # The table must be consistent with evaluate() cell by cell.
    node = PropImplies(P, Q)
    names, rows = truth_table(node, KLEENE)
    for binding, val in rows:
        assert evaluate(node, binding, KLEENE) == val
