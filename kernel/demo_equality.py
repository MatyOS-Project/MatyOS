"""
Phase C1b milestone: a real inductive proof, kernel-checked.

Theorem:  for all n : Nat,  n + 0 = n.

This is NOT true by computation alone: `add` recurses on its first argument, so
`add n 0` is stuck when `n` is a variable. The proof genuinely needs induction:

    base : add 0 0 = 0                      (holds by computation; refl)
    step : add k 0 = k  ==>  add (k+1) 0 = k+1
                                            (congruence `succ` applied to the IH)

We build the proof term, hand it to the trusted kernel, and check that its
inferred type is exactly the claim. If so, the theorem is PROVEN -- by the same
mechanism (type-checking a term) that Lean uses.
"""

from kernel.core import N, to_debruijn, infer, normalize, def_equal, pretty
from kernel.equality import setup_equality, EqS, reflS, cong_term
from kernel.demo_inductive import Nat, zero, succ, natrec, add, numeral

setup_equality()
cong = cong_term()


def add_(x, y):
    return N.App(N.App(add, x), y)


def infer_of(label, surface):
    ty = infer([], to_debruijn(surface))
    print(f"   {label} : {pretty(ty)}")
    return ty


# The proposition as a motive:  Q n  :=  (add n 0 = n)
Q = N.Lam("n", Nat, EqS(Nat, add_(N.Var("n"), zero), N.Var("n")))

# base : Q 0   i.e.   add 0 0 = 0.   Since add 0 0 computes to 0, refl works.
base = reflS(Nat, zero)

# step : (k : Nat) (ih : Q k) -> Q (succ k)
#   ih : add k 0 = k
#   goal : add (succ k) 0 = succ k   ==  succ (add k 0) = succ k   (by iota)
#   cong succ ih : succ (add k 0) = succ k
step = N.Lam("k", Nat,
         N.Lam("ih", EqS(Nat, add_(N.Var("k"), zero), N.Var("k")),
           N.App(N.App(N.App(N.App(N.App(N.App(
               cong, Nat), Nat), succ), add_(N.Var("k"), zero)),
               N.Var("k")), N.Var("ih"))))

# proof : (n : Nat) -> add n 0 = n      via   Nat.rec Q base step n
proof = N.Lam("n", Nat,
          N.App(N.App(N.App(N.App(natrec, Q), base), step), N.Var("n")))

# The claim we want the proof to inhabit.
claim = N.Pi("n", Nat, EqS(Nat, add_(N.Var("n"), zero), N.Var("n")))


if __name__ == "__main__":
    print("Building blocks (inferred types):")
    infer_of("cong", cong)
    infer_of("base", base)
    infer_of("step", step)

    print("\nTheorem:  forall n : Nat,  n + 0 = n")
    print(f"   claim : {pretty(to_debruijn(claim))}")
    proof_ty = infer([], to_debruijn(proof))
    print(f"   proof type : {pretty(proof_ty)}")

    if def_equal(proof_ty, to_debruijn(claim)):
        print("   [QED] proof type-checks against the claim -- PROVEN by induction")
    else:
        print("   [FAIL] proof does not have the claimed type")

    # sanity spot-checks of the two cases the induction combines
    print("\nUnderlying computations:")
    print(f"   add 0 0 normalizes to : {pretty(normalize(to_debruijn(add_(numeral(0), zero))))}")
    print(f"   add 3 0 normalizes to : {pretty(normalize(to_debruijn(add_(numeral(3), zero))))}")
