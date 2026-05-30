"""
Inductive-types layer test suite (MatyOS kernel).
==================================================
Rigorous tests for `matyos.kernel.inductive`: declaring inductive types,
their constructors and recursors, computation via iota-reduction, parameterised
inductives, and strict-positivity rejection.

Author: Ahmed Hafdi
"""

import os
import sys

import pytest

# Ensure we can import from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matyos.kernel.core import (
    N, to_debruijn, infer, normalize, def_equal, pretty, Const, Univ, Pi,
    PositivityError, reset_environment,
)
from matyos.kernel.inductive import declare_inductive, REC


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _clean_env():
    """Isolate every test: a fresh, empty global environment."""
    reset_environment()
    yield
    reset_environment()


def declare_nat():
    """Nat : Type0 with zero and succ : Nat -> Nat (recursive)."""
    return declare_inductive(
        "Nat", [], 0,
        [("zero", []), ("succ", [("n", REC)])],
    )


def declare_bool():
    """Bool : Type0 with true, false."""
    return declare_inductive(
        "Bool", [], 0,
        [("true", []), ("false", [])],
    )


def numeral(k):
    """Build the surface Nat numeral for k: succ^k zero."""
    t = N.Const("zero")
    for _ in range(k):
        t = N.App(N.Const("succ"), t)
    return t


def add_surface():
    """fun (m n : Nat) => Nat.rec (fun _ => Nat) n (fun k ih => succ ih) m"""
    return N.Lam("m", N.Const("Nat"), N.Lam("n", N.Const("Nat"),
        N.App(N.App(N.App(N.App(N.Const("Nat.rec"),
            N.Lam("_", N.Const("Nat"), N.Const("Nat"))),    # motive: fun _ => Nat
            N.Var("n")),                                    # base case: n
            N.Lam("k", N.Const("Nat"),                      # step: fun k ih => succ ih
                N.Lam("ih", N.Const("Nat"),
                    N.App(N.Const("succ"), N.Var("ih"))))),
            N.Var("m"))))                                   # scrutinee: m


def mul_surface(add):
    """fun (m n : Nat) => Nat.rec (fun _ => Nat) zero (fun k ih => add n ih) m"""
    return N.Lam("m", N.Const("Nat"), N.Lam("n", N.Const("Nat"),
        N.App(N.App(N.App(N.App(N.Const("Nat.rec"),
            N.Lam("_", N.Const("Nat"), N.Const("Nat"))),
            N.Const("zero")),
            N.Lam("k", N.Const("Nat"),
                N.Lam("ih", N.Const("Nat"),
                    N.App(N.App(add, N.Var("n")), N.Var("ih"))))),
            N.Var("m"))))


def not_surface():
    """fun (b : Bool) => Bool.rec (fun _ => Bool) false true b"""
    return N.Lam("b", N.Const("Bool"),
        N.App(N.App(N.App(N.App(N.Const("Bool.rec"),
            N.Lam("_", N.Const("Bool"), N.Const("Bool"))),
            N.Const("false")),   # minor for `true`
            N.Const("true")),    # minor for `false`
            N.Var("b")))


# ---------------------------------------------------------------------------
# 1. Declaring Nat: type former, constructors, recursor
# ---------------------------------------------------------------------------
def test_nat_type_former_is_type0():
    declare_nat()
    # Nat : Type0, i.e. infer(Nat) == Univ(0).
    assert infer([], Const("Nat")) == Univ(0)


def test_nat_zero_has_type_nat():
    declare_nat()
    assert def_equal(infer([], Const("zero")), to_debruijn(N.Const("Nat")))


def test_nat_succ_is_nat_to_nat():
    declare_nat()
    expected = to_debruijn(N.Arrow(N.Const("Nat"), N.Const("Nat")))
    assert def_equal(infer([], Const("succ")), expected)


def test_nat_succ_application_typechecks():
    declare_nat()
    # succ zero : Nat
    one = to_debruijn(N.App(N.Const("succ"), N.Const("zero")))
    assert def_equal(infer([], one), to_debruijn(N.Const("Nat")))


def test_nat_rec_typechecks_to_a_pi_mentioning_motive():
    declare_nat()
    rec_ty = infer([], Const("Nat.rec"))
    # The recursor's type is a (dependent) function type.
    assert isinstance(normalize(rec_ty), Pi)
    rendered = pretty(rec_ty)
    # Motive eliminates into Type0 and the whole thing is structured as
    # (motive) -> (zero case) -> (succ case) -> (x : Nat) -> motive x.
    assert "Nat -> Type0" in rendered
    # The two minor-premise constructor names appear in the recursor type.
    assert "zero" in rendered and "succ" in rendered


def test_declare_inductive_returns_recursor_name():
    rec_name = declare_nat()
    assert rec_name == "Nat.rec"


# ---------------------------------------------------------------------------
# 2. Computation via iota-reduction: add, mul, Bool not
# ---------------------------------------------------------------------------
def test_add_type_is_nat_nat_nat():
    declare_nat()
    add = add_surface()
    expected = to_debruijn(
        N.Arrow(N.Const("Nat"), N.Arrow(N.Const("Nat"), N.Const("Nat"))))
    assert def_equal(infer([], to_debruijn(add)), expected)


def test_add_two_plus_three_is_five():
    declare_nat()
    add = add_surface()
    expr = N.App(N.App(add, numeral(2)), numeral(3))
    assert def_equal(to_debruijn(expr), to_debruijn(numeral(5)))


def test_add_is_not_off_by_one():
    # Guard against a vacuous test: 2 + 3 must NOT equal 6.
    declare_nat()
    add = add_surface()
    expr = N.App(N.App(add, numeral(2)), numeral(3))
    assert not def_equal(to_debruijn(expr), to_debruijn(numeral(6)))


def test_add_zero_identity():
    declare_nat()
    add = add_surface()
    expr = N.App(N.App(add, numeral(0)), numeral(4))
    assert def_equal(to_debruijn(expr), to_debruijn(numeral(4)))


def test_add_normal_form_is_succ_chain():
    declare_nat()
    add = add_surface()
    expr = N.App(N.App(add, numeral(1)), numeral(1))
    # 1 + 1 normalizes structurally to succ (succ zero).
    assert normalize(to_debruijn(expr)) == normalize(to_debruijn(numeral(2)))


def test_mul_three_times_four_is_twelve():
    declare_nat()
    add = add_surface()
    mul = mul_surface(add)
    expr = N.App(N.App(mul, numeral(3)), numeral(4))
    assert def_equal(to_debruijn(expr), to_debruijn(numeral(12)))


def test_mul_by_zero_is_zero():
    declare_nat()
    add = add_surface()
    mul = mul_surface(add)
    expr = N.App(N.App(mul, numeral(0)), numeral(5))
    assert def_equal(to_debruijn(expr), to_debruijn(numeral(0)))


def test_bool_type_former_is_type0():
    declare_bool()
    assert infer([], Const("Bool")) == Univ(0)


def test_bool_not_true_is_false():
    declare_bool()
    bnot = not_surface()
    expr = N.App(bnot, N.Const("true"))
    assert def_equal(to_debruijn(expr), to_debruijn(N.Const("false")))


def test_bool_not_false_is_true():
    declare_bool()
    bnot = not_surface()
    expr = N.App(bnot, N.Const("false"))
    assert def_equal(to_debruijn(expr), to_debruijn(N.Const("true")))


def test_bool_not_not_is_identity():
    declare_bool()
    bnot = not_surface()
    expr = N.App(bnot, N.App(bnot, N.Const("true")))
    assert def_equal(to_debruijn(expr), to_debruijn(N.Const("true")))


# ---------------------------------------------------------------------------
# 3. Parameterised inductive: List
# ---------------------------------------------------------------------------
def declare_list():
    return declare_inductive(
        "List", [("A", N.U(0))], 0,
        [("nil", []), ("cons", [("head", N.Var("A")), ("tail", REC)])],
    )


def test_list_type_former_is_type0_to_type0():
    declare_list()
    expected = to_debruijn(N.Arrow(N.U(0), N.U(0)))
    assert def_equal(infer([], Const("List")), expected)


def test_list_nil_type():
    declare_list()
    # nil : Pi (A : Type0), List A
    expected = to_debruijn(N.Pi("A", N.U(0), N.App(N.Const("List"), N.Var("A"))))
    assert def_equal(infer([], Const("nil")), expected)


def test_list_cons_type():
    declare_list()
    # cons : Pi (A : Type0), A -> List A -> List A
    expected = to_debruijn(N.Pi("A", N.U(0),
        N.Arrow(N.Var("A"),
            N.Arrow(N.App(N.Const("List"), N.Var("A")),
                    N.App(N.Const("List"), N.Var("A"))))))
    assert def_equal(infer([], Const("cons")), expected)


def test_list_cons_application_typechecks():
    # Build a concrete list over Bool and check it inhabits List Bool.
    declare_bool()
    declare_list()
    list_bool = N.App(N.Const("List"), N.Const("Bool"))
    nil_bool = N.App(N.Const("nil"), N.Const("Bool"))
    # cons Bool true (nil Bool)
    one = N.App(N.App(N.App(N.Const("cons"), N.Const("Bool")),
                      N.Const("true")), nil_bool)
    assert def_equal(infer([], to_debruijn(one)), to_debruijn(list_bool))


def test_list_rec_typechecks():
    declare_list()
    # The generated recursor must itself type-check (to a Pi).
    rec_ty = infer([], Const("List.rec"))
    assert isinstance(normalize(rec_ty), Pi)


# ---------------------------------------------------------------------------
# 4. Strict positivity: non-positive declarations are rejected
# ---------------------------------------------------------------------------
def test_positivity_rejects_negative_self_in_domain():
    # Bad with constructor arg of type (Bad -> Bad): negative occurrence.
    with pytest.raises(PositivityError):
        declare_inductive(
            "Bad", [], 0,
            [("mk", [("f", N.Arrow(N.Const("Bad"), N.Const("Bad")))])],
        )


def test_positivity_rejects_negative_occurrence_into_universe():
    # Bad2 with arg (Bad2 -> Type0): the inductive appears in a domain.
    with pytest.raises(PositivityError):
        declare_inductive(
            "Bad2", [], 0,
            [("mk", [("f", N.Arrow(N.Const("Bad2"), N.U(0)))])],
        )


def test_positivity_rejected_declaration_registers_nothing():
    # Positivity is checked before anything is registered, so the failed
    # constant must not leak into the environment.
    with pytest.raises(PositivityError):
        declare_inductive(
            "Leaky", [], 0,
            [("mk", [("f", N.Arrow(N.Const("Leaky"), N.Const("Leaky")))])],
        )
    from matyos.kernel.core import TypeError_
    with pytest.raises(TypeError_):
        infer([], Const("Leaky"))


def test_positivity_accepts_bare_recursion_via_REC():
    # The legitimate counterpart: direct recursion through REC is fine.
    declare_inductive(
        "Tree", [], 0,
        [("leaf", []), ("node", [("l", REC), ("r", REC)])],
    )
    assert infer([], Const("Tree")) == Univ(0)
