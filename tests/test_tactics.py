"""Tests for the tactic engine (by / intro / exact / assumption / refl).

The tactic engine is untrusted: it builds a term the kernel re-checks, so a
correct script yields a PROVEN theorem and a bogus one is caught."""

import pytest

from matyos.kernel import core
from matyos.frontend.surface import run_source, Checker
from matyos.frontend.tactics import run_tactics, TacticError
from matyos.kernel.core import N, to_debruijn, infer, def_equal


@pytest.fixture(autouse=True)
def _isolate():
    core.reset_environment()
    yield
    core.reset_environment()


def run(prog):
    c = Checker()
    c.run_text(prog, echo=False)
    return c


def test_intro_exact_modus_ponens():
    c = run("""
theorem mp : forall (A : Type), forall (B : Type), (A -> B) -> A -> B
proof mp := by intro A B f a exact f a qed
""")
    assert c.failures == 0 and "mp" in c.proven


def test_assumption_closes_goal():
    c = run("""
theorem idp : forall (A : Type), A -> A
proof idp := by intro A x assumption qed
""")
    assert c.failures == 0 and "idp" in c.proven


def test_refl_closes_equality():
    c = run("""
inductive Nat : Type := | zero : Nat | succ : Nat -> Nat
theorem rz : Eq Nat zero zero
proof rz := by refl qed
""")
    assert c.failures == 0 and "rz" in c.proven


def test_example_by_block():
    c = run("""
example : forall (A : Type), forall (B : Type), A -> B -> A := by
  intro A B a b
  exact a
qed
""")
    assert c.failures == 0


def test_tactic_built_term_is_kernel_checked():
    # the tactic engine only builds a term; the kernel decides validity
    goal = N.Pi("A", N.U(0), N.Arrow(N.Var("A"), N.Var("A")))
    term = run_tactics(goal, [("intro", ["A", "x"]), ("exact", N.Var("x"))])
    assert def_equal(infer([], to_debruijn(term)), to_debruijn(goal))


def test_unsolved_goal_is_a_failure():
    c = run("""
theorem t : forall (A : Type), A -> A
proof t := by intro A x qed
""")
    assert c.failures == 1 and "t" not in c.proven


def test_intro_on_non_function_errors():
    with pytest.raises(TacticError):
        run_tactics(N.U(0), [("intro", ["x"])])


def test_assumption_without_match_errors():
    # goal A -> B with only a : A in context; assumption can't close B
    goal = N.Pi("A", N.U(0), N.Pi("B", N.U(0),
               N.Arrow(N.Var("A"), N.Var("B"))))
    with pytest.raises(TacticError):
        run_tactics(goal, [("intro", ["A", "B", "a"]), ("assumption",)])


def test_refl_on_non_reflexive_errors():
    c = run("""
inductive Nat : Type := | zero : Nat | succ : Nat -> Nat
theorem bad : Eq Nat zero (succ zero)
proof bad := by refl qed
""")
    assert c.failures == 1 and "bad" not in c.proven


def test_wrong_exact_caught_by_kernel():
    c = run("""
inductive Nat : Type := | zero : Nat | succ : Nat -> Nat
theorem t : forall (A : Type), A -> A
proof t := by intro A x exact zero qed
""")
    assert c.failures == 1 and "t" not in c.proven
