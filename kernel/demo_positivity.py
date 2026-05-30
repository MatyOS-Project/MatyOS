"""
Phase C1c demo: strict-positivity guard, and a note on termination.

Soundness of an inductive logic depends on two well-formedness conditions:

  1. STRICT POSITIVITY of inductive declarations. Without it you can encode
     non-terminating / paradoxical types (e.g. `Bad` with `mk : (Bad -> Bad)
     -> Bad`) and prove `False`. The kernel now rejects these.

  2. TERMINATION of recursive definitions. In this kernel the ONLY way to
     define a recursive function is via a datatype's recursor (`D.rec`), which
     is structurally terminating by construction. There is no general `fix`
     primitive, so non-terminating definitions cannot be written in the first
     place. (A general structural-recursion checker arrives with surface-level
     `def` in a later phase.)
"""

from kernel.core import N, PositivityError
from kernel.inductive import declare_inductive, REC


def ok(title, thunk):
    try:
        thunk()
        print(f"   [ACCEPTED] {title}")
    except PositivityError as e:
        print(f"   [unexpectedly REJECTED] {title}: {e}")


def must_reject(title, thunk):
    try:
        thunk()
        print(f"   [UNSOUND! accepted] {title}")
    except PositivityError as e:
        print(f"   [REJECTED] {title}\n              reason: {e}")


if __name__ == "__main__":
    print("Positive inductives (should be accepted):")
    ok("Tree = leaf | node Tree Tree",
       lambda: declare_inductive(
           "Tree", params=[], univ=0,
           constructors=[("leaf", []),
                         ("node", [("l", REC), ("r", REC)])]))

    print("\nNon-positive inductives (must be rejected to stay sound):")
    must_reject("Bad = mk (Bad -> Bad)",
                lambda: declare_inductive(
                    "Bad", params=[], univ=0,
                    constructors=[("mk", [("f", N.Arrow(N.Const("Bad"),
                                                        N.Const("Bad")))])]))

    must_reject("Bad2 = mk (Bad2 -> Nat)  [negative occurrence]",
                lambda: declare_inductive(
                    "Bad2", params=[], univ=0,
                    constructors=[("mk", [("f", N.Arrow(N.Const("Bad2"),
                                                        N.U(0)))])]))
