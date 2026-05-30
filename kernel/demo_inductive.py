"""
Phase C1a demo: declare inductive types, derive recursors, and COMPUTE.

If `add 2 3` normalizes to `5`, the recursor's iota-reduction is working --
that is the proof that the kernel can now do arithmetic, not just logic.
"""

from kernel.core import (
    N, to_debruijn, infer, normalize, def_equal, pretty,
)
from kernel.inductive import declare_inductive, REC


def show_type(label, surface):
    term = to_debruijn(surface)
    ty = infer([], term)
    print(f"   {label} : {pretty(ty)}")
    return term


# --------------------------------------------------------------------------
# Nat : Type0   with   zero : Nat   and   succ : Nat -> Nat
# --------------------------------------------------------------------------
declare_inductive(
    "Nat", params=[], univ=0,
    constructors=[
        ("zero", []),
        ("succ", [("n", REC)]),
    ],
)

Nat = N.Const("Nat")
zero = N.Const("zero")
succ = N.Const("succ")
natrec = N.Const("Nat.rec")


def numeral(k):
    t = zero
    for _ in range(k):
        t = N.App(succ, t)
    return t


# add = fun (m n : Nat) => Nat.rec (fun _ => Nat) n (fun k ih => succ ih) m
motive_nat = N.Lam("_", Nat, Nat)
add = N.Lam("m", Nat, N.Lam("n", Nat,
        N.App(N.App(N.App(N.App(natrec, motive_nat),
                          N.Var("n")),
                    N.Lam("k", Nat, N.Lam("ih", Nat, N.App(succ, N.Var("ih"))))),
              N.Var("m"))))

# mul = fun (m n : Nat) => Nat.rec (fun _ => Nat) zero (fun k ih => add n ih) m
mul = N.Lam("m", Nat, N.Lam("n", Nat,
        N.App(N.App(N.App(N.App(natrec, motive_nat),
                          zero),
                    N.Lam("k", Nat, N.Lam("ih", Nat,
                          N.App(N.App(add, N.Var("n")), N.Var("ih"))))),
              N.Var("m"))))

# --------------------------------------------------------------------------
# Bool : Type0   with   true, false : Bool
# --------------------------------------------------------------------------
declare_inductive(
    "Bool", params=[], univ=0,
    constructors=[("true", []), ("false", [])],
)

Bool = N.Const("Bool")
btrue = N.Const("true")
bfalse = N.Const("false")
boolrec = N.Const("Bool.rec")

# not = fun (b : Bool) => Bool.rec (fun _ => Bool) false true b
not_b = N.Lam("b", Bool,
          N.App(N.App(N.App(N.App(boolrec, N.Lam("_", Bool, Bool)),
                            bfalse),
                      btrue),
                N.Var("b")))

# --------------------------------------------------------------------------
# List : Type0 -> Type0   (a parameterised inductive)
# --------------------------------------------------------------------------
declare_inductive(
    "List", params=[("A", N.U(0))], univ=0,
    constructors=[
        ("nil", []),
        ("cons", [("head", N.Var("A")), ("tail", REC)]),
    ],
)


def expect(label, got_surface, want_surface):
    got = normalize(to_debruijn(got_surface))
    want = normalize(to_debruijn(want_surface))
    ok = got == want
    print(f"   {label:18s} => {pretty(got):>10s}   {'[OK]' if ok else '[WRONG]'}")
    return ok


if __name__ == "__main__":
    print("Inferred types of the derived schemes:")
    show_type("Nat ", Nat)
    show_type("zero", zero)
    show_type("succ", succ)
    show_type("Nat.rec", natrec)
    show_type("add ", add)
    show_type("mul ", mul)
    show_type("not ", not_b)
    show_type("List", N.Const("List"))
    show_type("cons", N.Const("cons"))

    print("\nComputation by iota-reduction (the recursor actually runs):")
    expect("add 2 3", N.App(N.App(add, numeral(2)), numeral(3)), numeral(5))
    expect("add 0 4", N.App(N.App(add, numeral(0)), numeral(4)), numeral(4))
    expect("mul 3 4", N.App(N.App(mul, numeral(3)), numeral(4)), numeral(12))
    expect("not true", N.App(not_b, btrue), bfalse)
    expect("not false", N.App(not_b, bfalse), btrue)
    expect("not(not true)", N.App(not_b, N.App(not_b, btrue)), btrue)
