"""
Propositional equality and the J eliminator (Phase C1b).

`Eq A a b` is the type of proofs that `a` and `b` (both of type `A`) are equal.
Its only constructor is `refl A a : Eq A a a` (everything is equal to itself).
This is an *indexed* family: the constructor's result fixes both index
positions to the same `a`.

Its eliminator is the (based) J rule of Martin-Lof type theory:

    J : (A : Type) (a : A)
        (P : (b : A) -> Eq A a b -> Type)
        (d : P a (refl A a))
        (b : A) (e : Eq A a b)
      -> P b e

with the computation rule       J A a P d a (refl A a)  ==>  d.

J + refl is exactly the power needed to rewrite with equalities and to prove
congruence (`cong`), which in turn lets us close inductive proofs like
`n + 0 = n` (see kernel/demo_equality.py).

We declare Eq / refl / Eq.J as trusted primitives with their standard types and
register J's reduction. A fully general indexed-inductive engine that *derives*
these is a later milestone; the rules here are the textbook ones and sound.
"""

from kernel.core import (
    N, to_debruijn, Const, App, _spine, normalize,
    declare_const, register_reducer,
)


# ----- surface-syntax helpers -----
def EqS(A, x, y):
    return N.App(N.App(N.App(N.Const("Eq"), A), x), y)


def reflS(A, x):
    return N.App(N.App(N.Const("refl"), A), x)


def _papp(P, b, e):
    return N.App(N.App(P, b), e)


def setup_equality():
    """Register Eq, refl and the J eliminator in the global environment."""
    U0 = N.U(0)

    # Eq : (A : Type0) -> A -> A -> Type0
    eq_type = N.Pi("A", U0, N.Arrow(N.Var("A"), N.Arrow(N.Var("A"), U0)))
    declare_const("Eq", to_debruijn(eq_type))

    # refl : (A : Type0) (a : A) -> Eq A a a
    refl_type = N.Pi("A", U0,
                  N.Pi("a", N.Var("A"),
                    EqS(N.Var("A"), N.Var("a"), N.Var("a"))))
    declare_const("refl", to_debruijn(refl_type))

    # Eq.J : (A:Type0)(a:A)(P:(b:A)->Eq A a b->Type0)(d:P a (refl A a))
    #        (b:A)(e:Eq A a b) -> P b e
    j_type = N.Pi("A", U0,
              N.Pi("a", N.Var("A"),
                N.Pi("P", N.Pi("b", N.Var("A"),
                               N.Arrow(EqS(N.Var("A"), N.Var("a"), N.Var("b")), U0)),
                  N.Pi("d", _papp(N.Var("P"), N.Var("a"),
                                  reflS(N.Var("A"), N.Var("a"))),
                    N.Pi("b2", N.Var("A"),
                      N.Pi("e", EqS(N.Var("A"), N.Var("a"), N.Var("b2")),
                        _papp(N.Var("P"), N.Var("b2"), N.Var("e"))))))))
    declare_const("Eq.J", to_debruijn(j_type))

    # iota rule:  Eq.J A a P d b (refl _ _)  ==>  d
    def j_reduce(args):
        if len(args) < 6:
            return None
        e = normalize(args[5])
        e_head, _ = _spine(e)
        if isinstance(e_head, Const) and e_head.name == "refl":
            result = args[3]  # d
            for extra in args[6:]:
                result = App(result, extra)
            return result
        return None

    register_reducer("Eq.J", j_reduce)


def cong_term():
    """cong : (A B:Type0)(f:A->B)(a a':A) -> Eq A a a' -> Eq B (f a) (f a')

    Proof: based path induction (J) on the equality, with motive
    `fun b _ => Eq B (f a) (f b)`; the base case is `refl B (f a)`.
    Returned as surface syntax (convert with to_debruijn).
    """
    U0 = N.U(0)
    A, B, f, a, ap, e = (N.Var("A"), N.Var("B"), N.Var("f"),
                         N.Var("a"), N.Var("ap"), N.Var("e"))
    motive = N.Lam("b", A,
               N.Lam("_", EqS(A, a, N.Var("b")),
                 EqS(B, N.App(f, a), N.App(f, N.Var("b")))))
    body = N.App(N.App(N.App(N.App(N.App(N.App(
        N.Const("Eq.J"), A), a), motive),
        reflS(B, N.App(f, a))), ap), e)
    return N.Lam("A", U0,
             N.Lam("B", U0,
               N.Lam("f", N.Arrow(A, B),
                 N.Lam("a", A,
                   N.Lam("ap", A,
                     N.Lam("e", EqS(A, a, ap),
                       body))))))
