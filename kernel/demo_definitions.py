"""
Phase C2a demo: named definitions with delta-reduction.

`define(name, type, body)` type-checks the body against the declared type and
records it, so `Const(name)` unfolds (delta-reduces) during evaluation. This is
how a real library is built: lemmas and functions become named constants you
can reuse -- including theorems, which are just definitions whose type is a
proposition and whose body is a proof.
"""

from kernel.core import (
    N, to_debruijn, define, normalize, def_equal, pretty, infer, Const,
)
from kernel.demo_inductive import Nat, zero, succ, add as add_surface, numeral
from kernel.demo_equality import proof as nat_zero_proof, claim as nat_zero_claim

NatT = to_debruijn(Nat)


def arrow(a, b):
    return to_debruijn(N.Arrow(a, b))


if __name__ == "__main__":
    # define add : Nat -> Nat -> Nat  (body = the recursor-based function)
    define("add", arrow(Nat, N.Arrow(Nat, Nat)), to_debruijn(add_surface))
    print("   defined  add : " + pretty(infer([], Const("add"))))

    # define double : Nat -> Nat := fun n => add n n   (uses Const add)
    double_body = N.Lam("n", Nat, N.App(N.App(N.Const("add"), N.Var("n")),
                                        N.Var("n")))
    define("double", arrow(Nat, Nat), to_debruijn(double_body))
    print("   defined  double : " + pretty(infer([], Const("double"))))

    # delta + beta + iota all compose: double 3 = 6
    got = normalize(to_debruijn(N.App(N.Const("double"), numeral(3))))
    want = normalize(to_debruijn(numeral(6)))
    print(f"   double 3 = {pretty(got)}   {'[OK]' if got == want else '[WRONG]'}")

    # A THEOREM stored as a definition: its type is a proposition, its body a
    # proof. define() refuses it unless the proof actually checks.
    define("add_zero_right", to_debruijn(nat_zero_claim),
           to_debruijn(nat_zero_proof))
    print("   defined  add_zero_right : " + pretty(infer([], Const("add_zero_right"))))
    print("   [OK] theorem accepted into the environment as a checked definition")

    # And a bogus definition is rejected:
    try:
        define("bogus", arrow(Nat, Nat), to_debruijn(zero))  # zero : Nat, not Nat->Nat
        print("   [WRONG] bogus definition accepted")
    except Exception as e:
        print(f"   [REJECTED] bogus def (zero : Nat is not Nat -> Nat)")
