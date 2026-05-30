"""
Rigorous tests for the trusted kernel of the MatyOS dependent-type-theory
proof assistant (``matyos.kernel.core``).

The kernel implements a predicative dependent type theory with a universe
hierarchy plus an *impredicative* ``Prop`` (Lean-style ``Sort 0``). Terms use
de Bruijn indices, so alpha-equivalence is syntactic.

These tests exercise:
    * shift / subst on de Bruijn terms
    * normalize (beta) and def_equal (normal-form / definitional equality)
    * infer for sorts, the predicative ``max`` Pi rule and the impredicative
      ``Prop`` Pi rule
    * Curry-Howard proof terms (identity, K, modus ponens, composition)
    * error cases that must raise ``TypeError_``

Assertions are made semantic (isinstance + fields, or def_equal against an
independently-built expected term) rather than relying on pretty-print strings.
"""

import pytest

from matyos.kernel import core
from matyos.kernel.core import (
    N,
    to_debruijn,
    shift,
    subst,
    normalize,
    def_equal,
    infer,
    type_check,
    pretty,
    Var,
    Univ,
    PropSort,
    PROP,
    Const,
    Pi,
    Lam,
    App,
    TypeError_,
)


@pytest.fixture(autouse=True)
def isolate_environment():
    """Reset the kernel's global environment before every test."""
    core.reset_environment()
    yield
    core.reset_environment()


# ---------------------------------------------------------------------------
# Helpers for the named-surface Curry-Howard examples.
# ---------------------------------------------------------------------------
def U(i):
    return N.U(i)


def V(name):
    return N.Var(name)


# ===========================================================================
# shift
# ===========================================================================
class TestShift:
    def test_free_var_shifted_above_cutoff(self):
        assert shift(Var(0), 1, 0) == Var(1)
        assert shift(Var(3), 2, 0) == Var(5)

    def test_var_below_cutoff_untouched(self):
        # Var(0) is bound relative to cutoff 1, so it is not shifted.
        assert shift(Var(0), 1, 1) == Var(0)
        assert shift(Var(2), 5, 3) == Var(2)

    def test_negative_shift(self):
        assert shift(Var(3), -1, 0) == Var(2)

    def test_sorts_and_const_are_invariant(self):
        assert shift(Univ(2), 10, 0) == Univ(2)
        assert shift(PROP, 10, 0) == PROP
        assert shift(Const("foo"), 10, 0) == Const("foo")

    def test_pi_increments_cutoff_under_binder(self):
        # Pi(Var0, Var1): the domain Var0 is free at cutoff 0 -> shifts;
        # the codomain lives under one binder, so its cutoff is 1.
        term = Pi(Var(0), Var(1))
        shifted = shift(term, 1, 0)
        assert shifted == Pi(Var(1), Var(2))

    def test_lam_increments_cutoff_under_binder(self):
        # Lam(Univ0, Var0): body Var0 is bound -> not shifted (cutoff becomes 1).
        term = Lam(Univ(0), Var(0))
        assert shift(term, 3, 0) == Lam(Univ(0), Var(0))
        # Var1 in the body is free (refers outside the lambda) -> shifts.
        term2 = Lam(Univ(0), Var(1))
        assert shift(term2, 3, 0) == Lam(Univ(0), Var(4))

    def test_app_shifts_both_subterms(self):
        term = App(Var(0), Var(1))
        assert shift(term, 2, 0) == App(Var(2), Var(3))


# ===========================================================================
# subst
# ===========================================================================
class TestSubst:
    def test_replaces_matching_index(self):
        assert subst(Var(0), 0, Univ(5)) == Univ(5)

    def test_leaves_other_indices(self):
        assert subst(Var(1), 0, Univ(5)) == Var(1)

    def test_sorts_invariant(self):
        assert subst(Univ(0), 0, Var(9)) == Univ(0)
        assert subst(PROP, 0, Var(9)) == PROP

    def test_subst_under_binder_shifts_target_and_index(self):
        # Substituting s=Var(7) for index 0 inside a Lam: under the binder the
        # index becomes 1 and s is shifted to Var(8).
        term = Lam(Univ(0), Var(1))  # body Var1 refers to outer index 0
        result = subst(term, 0, Var(7))
        assert result == Lam(Univ(0), Var(8))

    def test_subst_app(self):
        term = App(Var(0), Var(0))
        assert subst(term, 0, Univ(3)) == App(Univ(3), Univ(3))


# ===========================================================================
# normalize / def_equal
# ===========================================================================
class TestNormalize:
    def test_beta_reduction(self):
        # (fun (x : Type0) => x) Type0  ==>  Type0
        redex = App(Lam(Univ(0), Var(0)), Univ(0))
        assert normalize(redex) == Univ(0)

    def test_nested_beta(self):
        # (fun x => (fun y => x) Type1) Type0  ==> Type0
        inner = App(Lam(Univ(1), Var(1)), Univ(1))
        redex = App(Lam(Univ(0), inner), Univ(0))
        assert normalize(redex) == Univ(0)

    def test_atomic_terms_are_their_own_normal_form(self):
        for t in (Var(2), Univ(4), PROP):
            assert normalize(t) == t

    def test_normalize_recurses_into_pi_and_lam(self):
        # The codomain of this Pi contains a redex that must be reduced.
        redex = App(Lam(Univ(0), Var(0)), Univ(0))
        term = Pi(Univ(0), redex)
        assert normalize(term) == Pi(Univ(0), Univ(0))

    def test_stuck_application_is_preserved(self):
        # Var(0) applied to Var(1) has no head lambda -> stays as an App.
        term = App(Var(0), Var(1))
        assert normalize(term) == App(Var(0), Var(1))


class TestDefEqual:
    def test_equal_normal_forms(self):
        redex = App(Lam(Univ(0), Var(0)), Univ(0))
        assert def_equal(redex, Univ(0)) is True

    def test_alpha_equivalence_is_syntactic(self):
        # Two lambdas that would differ only by bound-variable name are the
        # very same de Bruijn term, hence definitionally equal.
        a = Lam(Univ(0), Var(0))
        b = Lam(Univ(0), Var(0))
        assert def_equal(a, b) is True

    def test_distinct_terms_not_equal(self):
        assert def_equal(Univ(0), Univ(1)) is False
        assert def_equal(PROP, Univ(0)) is False


# ===========================================================================
# infer: sorts and Pi sort rules
# ===========================================================================
class TestInferSorts:
    def test_univ_typed_by_next_universe(self):
        assert infer([], Univ(0)) == Univ(1)
        assert infer([], Univ(3)) == Univ(4)

    def test_prop_typed_by_type0(self):
        assert infer([], PROP) == Univ(0)

    def test_const_uses_declared_type(self):
        core.declare_const("Nat", Univ(0))
        assert infer([], Const("Nat")) == Univ(0)


class TestPiSortRules:
    def test_impredicative_prop_codomain_stays_prop(self):
        # Pi (P : Prop), P  : Prop   (impredicative rule)
        term = to_debruijn(N.Pi("P", N.Prop(), V("P")))
        result = infer([], term)
        assert isinstance(result, PropSort)

    def test_impredicative_even_with_type_domain(self):
        # Pi (A : Type5)(P : Prop), P  -- a product whose *codomain inhabits
        # Prop* is itself Prop, regardless of how large the domain universe is.
        # Here the body P has sort Prop, so the impredicative rule fires even
        # though A : Type5. A predicative theory would force this into Type5.
        term = to_debruijn(N.Pi("A", N.U(5), N.Pi("P", N.Prop(), V("P"))))
        result = infer([], term)
        assert isinstance(result, PropSort)

    def test_predicative_max_for_type(self):
        # Pi (A : Type0), A   : Type1   (predicative: max(level(Type0)=0+? ...))
        # Here domain sort = Type1 (since A:Type0, Type0:Type1), codomain sort
        # = Type0 (A : Type0). max(1, 0) = 1.
        term = to_debruijn(N.Pi("A", N.U(0), V("A")))
        assert infer([], term) == Univ(1)

    def test_predicative_max_picks_larger_universe(self):
        # Pi (A : Type2), A  : Type3
        term = to_debruijn(N.Pi("A", N.U(2), V("A")))
        assert infer([], term) == Univ(3)

    def test_arrow_between_types(self):
        # Type0 -> Type0  : Type1
        term = to_debruijn(N.Arrow(N.U(0), N.U(0)))
        assert infer([], term) == Univ(1)


# ===========================================================================
# infer: variables in context
# ===========================================================================
class TestInferVar:
    def test_var_zero_is_nearest_binder_type(self):
        # In ctx [Type0], Var(0) : Type0 (shifted by index+1 = 1, but Type0 has
        # no free vars so it is unchanged).
        assert infer([Univ(0)], Var(0)) == Univ(0)

    def test_var_lookup_shifts_stored_type(self):
        # ctx = [Var(0)]  (the nearest binder has type "the binder before it").
        # infer Var(0) shifts the stored type by index+1 = 1: Var(0) -> Var(1).
        assert infer([Var(0)], Var(0)) == Var(1)


# ===========================================================================
# Curry-Howard: proof terms type-check to the expected propositions.
# ===========================================================================
class TestCurryHoward:
    def test_identity(self):
        # fun (A : Type0)(x : A) => x   :   Pi (A : Type0), A -> A
        proof = N.Lam("A", U(0), N.Lam("x", V("A"), V("x")))
        prop = N.Pi("A", U(0), N.Arrow(V("A"), V("A")))
        actual = infer([], to_debruijn(proof))
        expected = to_debruijn(prop)
        assert isinstance(actual, Pi)
        assert def_equal(actual, expected)

    def test_K_combinator(self):
        # fun (A B : Type0)(x : A)(y : B) => x : Pi A B, A -> B -> A
        proof = N.Lam(
            "A", U(0),
            N.Lam("B", U(0),
                  N.Lam("x", V("A"),
                        N.Lam("y", V("B"), V("x")))),
        )
        prop = N.Pi(
            "A", U(0),
            N.Pi("B", U(0),
                 N.Arrow(V("A"), N.Arrow(V("B"), V("A")))),
        )
        actual = infer([], to_debruijn(proof))
        assert def_equal(actual, to_debruijn(prop))

    def test_modus_ponens(self):
        # fun (A B : Type0)(f : A -> B)(a : A) => f a
        #   : Pi A B, (A -> B) -> A -> B
        proof = N.Lam(
            "A", U(0),
            N.Lam("B", U(0),
                  N.Lam("f", N.Arrow(V("A"), V("B")),
                        N.Lam("a", V("A"),
                              N.App(V("f"), V("a"))))),
        )
        prop = N.Pi(
            "A", U(0),
            N.Pi("B", U(0),
                 N.Arrow(N.Arrow(V("A"), V("B")),
                         N.Arrow(V("A"), V("B")))),
        )
        actual = infer([], to_debruijn(proof))
        assert def_equal(actual, to_debruijn(prop))

    def test_function_composition(self):
        # fun (A B C : Type0)(g : B -> C)(f : A -> B)(a : A) => g (f a)
        #   : Pi A B C, (B -> C) -> (A -> B) -> A -> C
        proof = N.Lam(
            "A", U(0),
            N.Lam("B", U(0),
                  N.Lam("C", U(0),
                        N.Lam("g", N.Arrow(V("B"), V("C")),
                              N.Lam("f", N.Arrow(V("A"), V("B")),
                                    N.Lam("a", V("A"),
                                          N.App(V("g"), N.App(V("f"), V("a")))))))),
        )
        prop = N.Pi(
            "A", U(0),
            N.Pi("B", U(0),
                 N.Pi("C", U(0),
                      N.Arrow(N.Arrow(V("B"), V("C")),
                              N.Arrow(N.Arrow(V("A"), V("B")),
                                      N.Arrow(V("A"), V("C")))))),
        )
        actual = infer([], to_debruijn(proof))
        assert def_equal(actual, to_debruijn(prop))

    def test_type_check_helper_accepts_valid_proof(self):
        proof = to_debruijn(N.Lam("A", U(0), N.Lam("x", V("A"), V("x"))))
        prop = to_debruijn(N.Pi("A", U(0), N.Arrow(V("A"), V("A"))))
        assert type_check(proof, prop) is True

    def test_type_check_helper_rejects_wrong_type(self):
        proof = to_debruijn(N.Lam("A", U(0), N.Lam("x", V("A"), V("x"))))
        # Claim it proves Pi A, A -> (A -> A) which is false.
        wrong = to_debruijn(
            N.Pi("A", U(0), N.Arrow(V("A"), N.Arrow(V("A"), V("A"))))
        )
        assert type_check(proof, wrong) is False


# ===========================================================================
# Error cases: the kernel must reject ill-typed terms.
# ===========================================================================
class TestErrors:
    def test_apply_non_function(self):
        # (Type0) Type0 -- the head is a sort, not a Pi.
        with pytest.raises(TypeError_):
            infer([], App(Univ(0), Univ(0)))

    def test_argument_type_mismatch(self):
        # identity-at-Type0 applied to Type0 itself: the lambda expects an
        # argument of type Type0, but Type0 : Type1, so the second App fails.
        ident_at_ty0 = to_debruijn(
            N.Lam("A", U(0), N.Lam("x", V("A"), V("x")))
        )
        applied_once = App(ident_at_ty0, Univ(0))  # fine: A := Type0
        with pytest.raises(TypeError_):
            infer([], App(applied_once, Univ(0)))  # x := Type0, but Type0:Type1

    def test_unbound_variable_out_of_range(self):
        with pytest.raises(TypeError_):
            infer([], Var(5))

    def test_unbound_variable_negative(self):
        with pytest.raises(TypeError_):
            infer([], Var(-1))

    def test_self_application_does_not_type_check(self):
        # fun (A : Type0)(x : A) => x x   -- x : A is not a function.
        bogus = to_debruijn(
            N.Lam("A", U(0), N.Lam("x", V("A"), N.App(V("x"), V("x"))))
        )
        with pytest.raises(TypeError_):
            infer([], bogus)

    def test_pi_domain_not_a_type(self):
        # Pi (_ : (fun x => x)), Type0 -- domain is a lambda, whose type is a
        # Pi (a function type), not a sort.
        bad_domain = Lam(Univ(0), Var(0))
        with pytest.raises(TypeError_):
            infer([], Pi(bad_domain, Univ(0)))

    def test_lambda_domain_not_a_type(self):
        with pytest.raises(TypeError_):
            infer([], Lam(Lam(Univ(0), Var(0)), Var(0)))

    def test_unknown_const_raises(self):
        with pytest.raises(TypeError_):
            infer([], Const("does_not_exist"))


# ===========================================================================
# Surface-syntax conversion sanity (so the Curry-Howard tests rest on
# well-understood foundations).
# ===========================================================================
class TestToDebruijn:
    def test_nearest_binding_wins(self):
        # fun (x : Type0) => fun (x : Type1) => x   -> body refers to inner x = Var(0)
        term = to_debruijn(N.Lam("x", U(0), N.Lam("x", U(1), V("x"))))
        assert term == Lam(Univ(0), Lam(Univ(1), Var(0)))

    def test_arrow_is_nondependent_pi(self):
        # A -> B with A,B closed sorts: codomain index does not capture domain.
        term = to_debruijn(N.Arrow(N.U(0), N.U(1)))
        assert term == Pi(Univ(0), Univ(1))

    def test_unknown_name_raises(self):
        with pytest.raises(TypeError_):
            to_debruijn(N.Var("nope"))

    def test_embedded_kernel_term_passes_through(self):
        assert to_debruijn(Univ(2)) == Univ(2)

    def test_prop_and_const_conversion(self):
        assert to_debruijn(N.Prop()) is PROP
        assert to_debruijn(N.Const("Nat")) == Const("Nat")


# ===========================================================================
# pretty: display only, but verify it produces a string for each term shape.
# ===========================================================================
class TestPretty:
    def test_basic_shapes(self):
        assert pretty(Univ(0)) == "Type0"
        assert pretty(PROP) == "Prop"
        assert pretty(Const("Nat")) == "Nat"

    def test_nondependent_pi_renders_as_arrow(self):
        # Type0 -> Type0
        text = pretty(to_debruijn(N.Arrow(N.U(0), N.U(0))))
        assert "->" in text
