"""
Demonstration: real proofs as typed terms, checked by the trusted kernel.

Each "theorem" is a TYPE; each "proof" is a TERM the kernel type-checks. If
`infer` returns the proposition's type without error, the proof is valid.
"""

from kernel.core import N, to_debruijn, infer, pretty, TypeError_


def check(title, surface_proof, claimed_reading):
    print(f"\n=== {title} ===")
    print(f"   claim : {claimed_reading}")
    term = to_debruijn(surface_proof)
    print(f"   proof : {pretty(term)}")
    try:
        ty = infer([], term)
        print(f"   TYPE  : {pretty(ty)}")
        print("   [OK] proof type-checks")
        return True
    except TypeError_ as e:
        print(f"   [REJECTED] {e}")
        return False


Type0 = N.U(0)


# ----------------------------------------------------------------------
# 1. Identity:  forall (A : Type), A -> A
#    proof:     fun (A : Type) => fun (x : A) => x
# ----------------------------------------------------------------------
identity = N.Lam("A", Type0,
              N.Lam("x", N.Var("A"),
                 N.Var("x")))

# ----------------------------------------------------------------------
# 2. K combinator / "A implies (B implies A)":
#    forall (A B : Type), A -> B -> A
#    proof: fun A B (a:A) (b:B) => a
# ----------------------------------------------------------------------
const_k = N.Lam("A", Type0,
            N.Lam("B", Type0,
              N.Lam("a", N.Var("A"),
                N.Lam("b", N.Var("B"),
                  N.Var("a")))))

# ----------------------------------------------------------------------
# 3. Modus ponens:  forall (A B : Type), (A -> B) -> A -> B
#    proof: fun A B (f : A -> B) (a : A) => f a
# ----------------------------------------------------------------------
modus_ponens = N.Lam("A", Type0,
                 N.Lam("B", Type0,
                   N.Lam("f", N.Arrow(N.Var("A"), N.Var("B")),
                     N.Lam("a", N.Var("A"),
                       N.App(N.Var("f"), N.Var("a"))))))

# ----------------------------------------------------------------------
# 4. Function composition: forall A B C, (B->C) -> (A->B) -> A -> C
#    proof: fun A B C (g:B->C) (f:A->B) (x:A) => g (f x)
# ----------------------------------------------------------------------
compose = N.Lam("A", Type0,
            N.Lam("B", Type0,
              N.Lam("C", Type0,
                N.Lam("g", N.Arrow(N.Var("B"), N.Var("C")),
                  N.Lam("f", N.Arrow(N.Var("A"), N.Var("B")),
                    N.Lam("x", N.Var("A"),
                      N.App(N.Var("g"), N.App(N.Var("f"), N.Var("x")))))))))

# ----------------------------------------------------------------------
# 5. A BOGUS proof the kernel must REJECT:
#    fun (A:Type) (x:A) => x x      -- applies x:A as if it were a function
# ----------------------------------------------------------------------
bogus = N.Lam("A", Type0,
          N.Lam("x", N.Var("A"),
            N.App(N.Var("x"), N.Var("x"))))


if __name__ == "__main__":
    print("Kernel self-test: proofs are terms; the kernel decides validity.")
    check("Identity", identity, "forall A, A -> A")
    check("K  (A -> B -> A)", const_k, "forall A B, A -> B -> A")
    check("Modus ponens", modus_ponens, "forall A B, (A -> B) -> A -> B")
    check("Composition", compose, "forall A B C, (B->C) -> (A->B) -> A -> C")
    check("Bogus (self-application)", bogus, "should be REJECTED as ill-typed")
