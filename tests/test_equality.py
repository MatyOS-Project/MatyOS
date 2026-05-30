"""
Propositional equality and the J eliminator — kernel tests (Phase C1b).
=======================================================================
Rigorous checks that `matyos.kernel.equality` registers Eq / refl / Eq.J with
their textbook MLTT types, that J's iota rule computes, that `cong` type-checks,
and — the milestone — that a *real* induction proof of `forall n, n + 0 = n`
is accepted by the trusted kernel while a false variant is rejected.

Author: Ahmed Hafdi — MatyOS / El
"""

import os
import sys

import pytest

# Ensure we can import from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matyos.kernel.core import (
    N, to_debruijn, infer, normalize, def_equal, pretty, define,
    Const, reset_environment, TypeError_,
)
from matyos.kernel.equality import setup_equality, EqS, reflS, cong_term
from matyos.kernel.inductive import declare_inductive, REC


# --------------------------------------------------------------------------
# Fixture: a clean environment with Eq/refl/Eq.J registered before each test.
# --------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def fresh_env():
    reset_environment()
    setup_equality()
    yield


# --------------------------------------------------------------------------
# Helpers shared by several tests.
# --------------------------------------------------------------------------
NAT = N.Const("Nat")
ZERO = N.Const("zero")
SUCC = N.Const("succ")


def _declare_nat():
    """Declare Nat with constructors zero, succ : Nat -> Nat (REC)."""
    return declare_inductive("Nat", [], 0,
                             [("zero", []), ("succ", [("n", REC)])])


def _define_add():
    """Define add by recursion on the first argument (cf. stdlib/arith.elk):
        add m n = Nat.rec (fun _ => Nat) n (fun k ih => succ ih) m
    """
    add_body = N.App(N.App(N.App(N.App(
        N.Const("Nat.rec"),
        N.Lam("_", NAT, NAT)),                       # motive: fun _ : Nat => Nat
        N.Var("n")),                                  # base   : n
        N.Lam("k", NAT, N.Lam("ih", NAT,              # step   : fun k ih => succ ih
               N.App(SUCC, N.Var("ih"))))),
        N.Var("m"))                                   # scrutinee: m
    add_lam = N.Lam("m", NAT, N.Lam("n", NAT, add_body))
    add_ty = to_debruijn(N.Arrow(NAT, N.Arrow(NAT, NAT)))
    define("add", add_ty, to_debruijn(add_lam))


def _addS(a, b):
    return N.App(N.App(N.Const("add"), a), b)


def _define_cong():
    """Register cong as a checked global definition from cong_term()."""
    cong_core = to_debruijn(cong_term())
    cong_ty = infer([], cong_core)
    define("cong", cong_ty, cong_core)


# --------------------------------------------------------------------------
# 1. setup_equality registers Eq / refl / Eq.J with the expected types.
# --------------------------------------------------------------------------
def test_eq_type():
    # Eq : (A : Type0) -> A -> A -> Type0
    eq_ty = infer([], Const("Eq"))
    expected = to_debruijn(
        N.Pi("A", N.U(0), N.Arrow(N.Var("A"), N.Arrow(N.Var("A"), N.U(0)))))
    assert def_equal(eq_ty, expected)


def test_refl_type():
    # refl : (A : Type0) (a : A) -> Eq A a a
    refl_ty = infer([], Const("refl"))
    expected = to_debruijn(
        N.Pi("A", N.U(0),
          N.Pi("a", N.Var("A"),
            EqS(N.Var("A"), N.Var("a"), N.Var("a")))))
    assert def_equal(refl_ty, expected)


def test_j_type():
    # Eq.J : (A:Type0)(a:A)(P:(b:A)->Eq A a b->Type0)(d:P a (refl A a))
    #        (b:A)(e:Eq A a b) -> P b e
    j_ty = infer([], Const("Eq.J"))
    expected = to_debruijn(
        N.Pi("A", N.U(0),
          N.Pi("a", N.Var("A"),
            N.Pi("P", N.Pi("b", N.Var("A"),
                          N.Arrow(EqS(N.Var("A"), N.Var("a"), N.Var("b")), N.U(0))),
              N.Pi("d", N.App(N.App(N.Var("P"), N.Var("a")),
                              reflS(N.Var("A"), N.Var("a"))),
                N.Pi("b2", N.Var("A"),
                  N.Pi("e", EqS(N.Var("A"), N.Var("a"), N.Var("b2")),
                    N.App(N.App(N.Var("P"), N.Var("b2")), N.Var("e")))))))))
    assert def_equal(j_ty, expected)
    # also a couple of robustness substring checks on the pretty form
    s = pretty(normalize(j_ty))
    assert "Eq" in s and "refl" in s


def test_constants_are_sorts():
    # The declared types of Eq, refl, Eq.J must each themselves be well-typed
    # (their type is a sort).
    for nm in ("Eq", "refl", "Eq.J"):
        sort = normalize(infer([], infer([], Const(nm))))
        assert pretty(sort).startswith("Type"), f"{nm} type's type is not a sort"


# --------------------------------------------------------------------------
# 2. cong type-checks to the expected congruence type.
# --------------------------------------------------------------------------
def test_cong_type():
    cong_core = to_debruijn(cong_term())
    cong_ty = infer([], cong_core)
    # cong : (A B:Type0)(f:A->B)(a a':A) -> Eq A a a' -> Eq B (f a) (f a')
    expected = to_debruijn(
        N.Pi("A", N.U(0),
          N.Pi("B", N.U(0),
            N.Pi("f", N.Arrow(N.Var("A"), N.Var("B")),
              N.Pi("a", N.Var("A"),
                N.Pi("ap", N.Var("A"),
                  N.Arrow(EqS(N.Var("A"), N.Var("a"), N.Var("ap")),
                          EqS(N.Var("B"),
                              N.App(N.Var("f"), N.Var("a")),
                              N.App(N.Var("f"), N.Var("ap"))))))))))
    assert def_equal(cong_ty, expected)


# --------------------------------------------------------------------------
# 3. J computes: Eq.J A a P d a (refl A a)  ==>  d.
# --------------------------------------------------------------------------
def test_j_reduces_to_d():
    _declare_nat()
    # Non-dependent motive P = fun b e => Nat, base d = zero.
    P = N.Lam("b", NAT,
          N.Lam("e", EqS(NAT, ZERO, N.Var("b")), NAT))
    jterm = N.App(N.App(N.App(N.App(N.App(N.App(
        N.Const("Eq.J"), NAT), ZERO), P), ZERO),    # A a P d
        ZERO),                                       # b
        reflS(NAT, ZERO))                            # e = refl Nat zero
    result = normalize(to_debruijn(jterm))
    # contractum is the base d = zero
    assert result == normalize(to_debruijn(ZERO))
    assert def_equal(to_debruijn(jterm), to_debruijn(ZERO))
    # and the whole application is well-typed (its type is the motive at zero)
    jty = infer([], to_debruijn(jterm))
    assert def_equal(jty, to_debruijn(NAT))


def test_j_does_not_fire_on_neutral():
    # With a free (variable) equality proof, J is stuck — must NOT reduce to d.
    _declare_nat()
    P = N.Lam("b", NAT, N.Lam("e", EqS(NAT, ZERO, N.Var("b")), NAT))
    # e : Eq Nat zero b   (b, e are context variables 1, 0)
    A_db = to_debruijn(NAT)
    eq_db = to_debruijn(EqS(NAT, ZERO, N.Var("b")), ["b"])  # under one binder
    ctx = [eq_db, A_db]  # ctx[0] = type of Var0 (e), ctx[1] = type of Var1 (b)
    # Build core term directly: Eq.J Nat zero P b e  with b=Var1, e=Var0
    from matyos.kernel.core import App as CApp, Var as CVar
    jcore = CApp(CApp(CApp(CApp(CApp(CApp(
        Const("Eq.J"), Const("Nat")), Const("zero")),
        to_debruijn(P)), Const("zero")),
        CVar(1)),    # b
        CVar(0))     # e (neutral)
    nf = normalize(jcore)
    # head should still be Eq.J — i.e. it did not collapse to `zero`.
    assert nf != Const("zero")
    assert "Eq.J" in pretty(nf)
    # And it type-checks against the motive applied to b/e.
    ty = infer(ctx, jcore)
    assert def_equal(ty, to_debruijn(NAT))


# --------------------------------------------------------------------------
# 4. add computes (smoke test for the recursor we rely on in the milestone).
# --------------------------------------------------------------------------
def test_add_computes():
    _declare_nat()
    _define_add()
    two = N.App(SUCC, N.App(SUCC, ZERO))
    three = N.App(SUCC, N.App(SUCC, N.App(SUCC, ZERO)))
    five = N.App(SUCC, N.App(SUCC, N.App(SUCC, N.App(SUCC, N.App(SUCC, ZERO)))))
    assert def_equal(to_debruijn(_addS(two, three)), to_debruijn(five))


# --------------------------------------------------------------------------
# 5. THE MILESTONE: a genuine induction proof of  forall n, n + 0 = n.
# --------------------------------------------------------------------------
def test_milestone_add_zero_right():
    _declare_nat()
    _define_add()
    _define_cong()

    # motive : fun m => Eq Nat (add m zero) m
    motive = N.Lam("m", NAT, EqS(NAT, _addS(N.Var("m"), ZERO), N.Var("m")))
    # base : refl Nat zero  (since add zero zero reduces to zero)
    base = reflS(NAT, ZERO)
    # step : fun k (ih : Eq Nat (add k zero) k) =>
    #            cong Nat Nat succ (add k zero) k ih
    step = N.Lam("k", NAT,
            N.Lam("ih", EqS(NAT, _addS(N.Var("k"), ZERO), N.Var("k")),
              N.App(N.App(N.App(N.App(N.App(N.App(
                N.Const("cong"), NAT), NAT), SUCC),
                _addS(N.Var("k"), ZERO)), N.Var("k")), N.Var("ih"))))
    proof = N.Lam("n", NAT,
              N.App(N.App(N.App(N.App(
                N.Const("Nat.rec"), motive), base), step), N.Var("n")))

    claim = to_debruijn(
        N.Pi("n", NAT, EqS(NAT, _addS(N.Var("n"), ZERO), N.Var("n"))))

    inferred = infer([], to_debruijn(proof))
    assert def_equal(inferred, claim), (
        f"proof has type {pretty(normalize(inferred))}, "
        f"expected {pretty(normalize(claim))}")

    # And as a checked global definition (define re-verifies body : type).
    define("add_zero_right", claim, to_debruijn(proof))
    assert def_equal(infer([], Const("add_zero_right")), claim)


# --------------------------------------------------------------------------
# 6. NEGATIVE: a false claim must NOT type-check.
# --------------------------------------------------------------------------
def test_negative_false_claim_rejected():
    """`forall n, Eq Nat (add n zero) (succ n)` is false; the analogous
    induction attempt must be rejected by the kernel."""
    _declare_nat()
    _define_add()
    _define_cong()

    # False motive: add m zero = succ m.
    false_motive = N.Lam("m", NAT,
        EqS(NAT, _addS(N.Var("m"), ZERO), N.App(SUCC, N.Var("m"))))
    base = reflS(NAT, ZERO)  # would need : Eq Nat zero (succ zero) — false
    step = N.Lam("k", NAT,
            N.Lam("ih", EqS(NAT, _addS(N.Var("k"), ZERO), N.Var("k")),
              N.App(N.App(N.App(N.App(N.App(N.App(
                N.Const("cong"), NAT), NAT), SUCC),
                _addS(N.Var("k"), ZERO)), N.Var("k")), N.Var("ih"))))
    bad = N.Lam("n", NAT,
            N.App(N.App(N.App(N.App(
              N.Const("Nat.rec"), false_motive), base), step), N.Var("n")))

    with pytest.raises(TypeError_):
        infer([], to_debruijn(bad))


def test_negative_refl_wrong_type_rejected():
    """`refl Nat zero` has type `Eq Nat zero zero`; it is NOT a proof of
    `Eq Nat zero (succ zero)`. Either infer rejects the annotated definition,
    or the inferred type is not def_equal to the false claim."""
    _declare_nat()
    one = N.App(SUCC, ZERO)
    false_claim = to_debruijn(EqS(NAT, ZERO, one))

    refl_core = to_debruijn(reflS(NAT, ZERO))
    inferred = infer([], refl_core)
    # The true type is Eq Nat zero zero, not the false claim.
    assert not def_equal(inferred, false_claim)

    # define() must reject the mis-annotated proof.
    with pytest.raises(TypeError_):
        define("bogus", false_claim, refl_core)
