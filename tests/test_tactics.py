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


def test_rewrite_with_hypothesis():
    c = run("""
inductive Nat : Type := | zero : Nat | succ : Nat -> Nat
theorem cong_succ : forall (a : Nat), forall (b : Nat), Eq Nat a b -> Eq Nat (succ a) (succ b)
proof cong_succ := by intro a b h rewrite h refl qed
""")
    assert c.failures == 0 and "cong_succ" in c.proven


def test_rewrite_then_assumption():
    c = run("""
inductive Nat : Type := | zero : Nat | succ : Nat -> Nat
theorem rw : forall (a : Nat), forall (b : Nat), Eq Nat a b -> Eq Nat b b -> Eq Nat a b
proof rw := by intro a b h1 h2 rewrite h1 assumption qed
""")
    assert c.failures == 0 and "rw" in c.proven


def test_rewrite_non_equality_errors():
    from matyos.kernel.core import N
    # rewriting with a non-equality hypothesis must fail (not certify nonsense)
    c = run("""
inductive Nat : Type := | zero : Nat | succ : Nat -> Nat
theorem bad : forall (a : Nat), Eq Nat a a
proof bad := by intro a rewrite a refl qed
""")
    assert c.failures == 1 and "bad" not in c.proven


def test_induction_proves_add_zero():
    c = run("""
inductive Nat : Type := | zero : Nat | succ : Nat -> Nat
def add (m : Nat) (n : Nat) : Nat := Nat.rec (fun (_ : Nat) => Nat) n (fun (k : Nat) (ih : Nat) => succ ih) m
theorem add_zero_r : forall (n : Nat), Eq Nat (add n zero) n
proof add_zero_r := by
  induction n
  refl
  intro k ih
  rewrite ih
  refl
qed
""")
    assert c.failures == 0 and "add_zero_r" in c.proven


def test_induction_on_bool():
    c = run("""
inductive Bool : Type := | true : Bool | false : Bool
def neg (b : Bool) : Bool := Bool.rec (fun (_ : Bool) => Bool) false true b
theorem neg_neg : forall (b : Bool), Eq Bool (neg (neg b)) b
proof neg_neg := by induction b refl refl qed
""")
    assert c.failures == 0 and "neg_neg" in c.proven


def test_induction_too_few_cases_fails():
    # only handling the base case leaves the step goal open -> failure
    c = run("""
inductive Nat : Type := | zero : Nat | succ : Nat -> Nat
def add (m : Nat) (n : Nat) : Nat := Nat.rec (fun (_ : Nat) => Nat) n (fun (k : Nat) (ih : Nat) => succ ih) m
theorem t : forall (n : Nat), Eq Nat (add n zero) n
proof t := by induction n refl qed
""")
    assert c.failures == 1 and "t" not in c.proven


_EQ = """
inductive Nat : Type := | zero : Nat | succ : Nat -> Nat
def cong (A : Type) (B : Type) (f : A -> B) (a : A) (b : A) (e : Eq A a b) : Eq B (f a) (f b) :=
  Eq.J A a (fun (x : A) (_ : Eq A a x) => Eq B (f a) (f x)) (refl B (f a)) b e
def trans (A : Type) (a : A) (b : A) (c : A) (e1 : Eq A a b) (e2 : Eq A b c) : Eq A a c :=
  Eq.J A b (fun (x : A) (_ : Eq A b x) => Eq A a x) e1 c e2
"""


def test_apply_premise_becomes_subgoal():
    c = run(_EQ + """
theorem t : forall (a : Nat), forall (b : Nat), Eq Nat a b -> Eq Nat (succ a) (succ b)
proof t := by intro a b h apply (cong Nat Nat succ a b) exact h qed
""")
    assert c.failures == 0 and "t" in c.proven


def test_apply_infers_arguments():
    # cong's a,b are NOT given; matching the conclusion against the goal infers them
    c = run(_EQ + """
theorem t : forall (a : Nat), forall (b : Nat), Eq Nat a b -> Eq Nat (succ a) (succ b)
proof t := by intro a b h apply (cong Nat Nat succ) exact h qed
""")
    assert c.failures == 0 and "t" in c.proven


def test_apply_chains_with_two_subgoals():
    c = run(_EQ + """
theorem t : forall (a : Nat), forall (b : Nat), forall (c : Nat),
  Eq Nat a b -> Eq Nat b c -> Eq Nat a c
proof t := by intro a b c h1 h2 apply (trans Nat a b c) exact h1 exact h2 qed
""")
    assert c.failures == 0 and "t" in c.proven


def test_apply_mismatch_fails():
    c = run(_EQ + """
theorem bad : forall (a : Nat), Eq Nat (succ a) a
proof bad := by intro a apply (cong Nat Nat succ a a) qed
""")
    assert c.failures == 1 and "bad" not in c.proven


def test_auto_proves_combinators():
    c = run("""
theorem id_thm : forall (A : Type), A -> A
proof id_thm := by auto qed
theorem mp : forall (A : Type), forall (B : Type), (A -> B) -> A -> B
proof mp := by auto qed
theorem comp : forall (A : Type), forall (B : Type), forall (C : Type), (B -> C) -> (A -> B) -> A -> C
proof comp := by auto qed
theorem k : forall (A : Type), forall (B : Type), A -> B -> A
proof k := by auto qed
""")
    assert c.failures == 0
    for n in ("id_thm", "mp", "comp", "k"):
        assert n in c.proven


def test_auto_fails_on_non_theorem():
    c = run("""
theorem bad : forall (A : Type), forall (B : Type), A -> B
proof bad := by auto qed
""")
    assert c.failures == 1 and "bad" not in c.proven


def test_proofsession_stepwise():
    # the interactive LLM-loop harness: inspect goals, step a tactic, repeat
    from matyos.frontend.tactics import ProofSession
    from matyos.frontend.surface import setup_equality
    from matyos.kernel.core import N, to_debruijn, infer, def_equal
    core.reset_environment()
    setup_equality()
    goal = N.Pi("A", N.U(0), N.Arrow(N.Var("A"), N.Var("A")))
    s = ProofSession(to_debruijn(goal))
    assert s.goals_json()[0]["hypotheses"] == []
    s.step(("intro", ["A", "x"]))
    js = s.goals_json()[0]
    assert {"name": "x", "type": "A"} in js["hypotheses"]
    assert js["target"] == "A"
    s.step(("assumption",))
    assert s.is_done()
    assert def_equal(infer([], s.proof()), to_debruijn(goal))


def test_proofsession_unsolved_errors():
    from matyos.frontend.tactics import ProofSession, TacticError
    from matyos.kernel.core import N, to_debruijn
    s = ProofSession(to_debruijn(N.Pi("A", N.U(0), N.Arrow(N.Var("A"), N.Var("A")))))
    s.step(("intro", ["A", "x"]))
    import pytest as _pytest
    with _pytest.raises(TacticError):
        s.proof()   # still one open goal
