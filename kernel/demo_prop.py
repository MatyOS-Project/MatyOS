"""
Phase C2b demo: impredicative Prop.

`Prop` is the sort of propositions. Its defining feature is IMPREDICATIVITY:
a `Pi` whose codomain is in `Prop` is itself in `Prop`, no matter how large the
domain is. This is what lets propositions quantify over all propositions
(e.g. `False := forall (P : Prop), P`) while staying in `Prop`.

Contrast with the predicative `Type` tower, where quantifying over `Type i`
forces you up to `Type (i+1)`.
"""

from kernel.core import N, to_debruijn, infer, normalize, pretty, define, Const

U0 = N.U(0)
Prop = N.Prop()


def show(label, surface):
    term = to_debruijn(surface)
    print(f"   {label:34s} : {pretty(infer([], term))}")


if __name__ == "__main__":
    print("Sorts:")
    show("Prop", Prop)                       # Prop : Type0

    print("\nImpredicative Prop vs predicative Type:")
    # False := forall (P : Prop), P     -- stays in Prop (impredicative)
    false_prop = N.Pi("P", Prop, N.Var("P"))
    show("forall (P:Prop), P   [= False]", false_prop)
    # forall (A : Type0), A             -- jumps to Type1 (predicative)
    show("forall (A:Type0), A", N.Pi("A", U0, N.Var("A")))

    print("\nDefining logical primitives in Prop:")
    define("False", to_debruijn(Prop), to_debruijn(false_prop))
    print("   False : " + pretty(infer([], Const("False"))))

    # not := fun (A : Prop) => A -> False
    not_def = N.Lam("A", Prop, N.Arrow(N.Var("A"), N.Const("False")))
    define("not", to_debruijn(N.Arrow(Prop, Prop)), to_debruijn(not_def))
    print("   not   : " + pretty(infer([], Const("not"))))

    # ex falso: fun (P:Prop) (h:False) => h P    :  forall P, False -> P
    efq = N.Lam("P", Prop,
            N.Lam("h", N.Const("False"),
              N.App(N.Var("h"), N.Var("P"))))
    efq_type = N.Pi("P", Prop, N.Arrow(N.Const("False"), N.Var("P")))
    define("absurd", to_debruijn(efq_type), to_debruijn(efq))
    print("   absurd: " + pretty(infer([], Const("absurd"))) + "   [ex falso quodlibet]")
    print("   [OK] impredicative Prop works; logical primitives type-check")
