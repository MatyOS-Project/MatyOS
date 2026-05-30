"""
Inductive types and recursors (Phase C1a).

This is the step from "logic" to "mathematics": it lets us declare datatypes
like `Nat`, `Bool`, `List`, derive their induction/recursion principles
(recursors), and *compute* with them (iota-reduction, implemented in
`kernel/core.normalize`).

An inductive declaration is given as Python data; from it we generate, as
genuine kernel terms, the *types* of:
  * the type former            D : (params) -> Type u
  * each constructor           c_i : (params) -> (args) -> D params
  * the recursor               D.rec : (params) (motive) (minors) (x) -> motive x
and we register the recursor's reduction rule with the kernel.

Supported fragment (sound and already enough for real arithmetic):
  * parameters (e.g. `List (A : Type)`),
  * constructor arguments that are either non-recursive or *first-order
    recursive* (the inductive applied to its own parameters, e.g. `Nat` in
    `succ : Nat -> Nat`).
Indexed families (e.g. propositional equality `Eq`) and universe polymorphism
are the next milestones (C1b, C2).
"""

from kernel.core import (
    N, to_debruijn, infer, normalize, pretty,
    declare_const, register_recursor, Univ, TypeError_,
)

# Sentinel marking a recursive constructor argument (type = the inductive
# applied to its parameters).
REC = object()


def _pi(telescope, body):
    """Build a nested Pi from a telescope [(name, type), ...]."""
    result = body
    for name, ty in reversed(telescope):
        result = N.Pi(name, ty, result)
    return result


def _app_chain(head, args):
    for a in args:
        head = N.App(head, a)
    return head


def declare_inductive(name, params, univ, constructors, motive_univ=0,
                      check=True):
    """Declare an inductive type and register its constructors + recursor.

    params        : [(param_name, surface_type), ...]
    univ          : the type former lands in Type<univ>
    constructors  : [(ctor_name, [(arg_name, surface_type | REC), ...]), ...]
    motive_univ   : universe the recursor's motive eliminates into
    """
    param_names = [p for p, _ in params]
    # The inductive applied to its parameters: `D p1 ... pm`.
    applied = _app_chain(N.Const(name), [N.Var(p) for p in param_names])

    # 1. The type former:  D : (params) -> Type univ
    former_type = _pi(params, N.U(univ))
    declare_const(name, to_debruijn(former_type))

    # 2. Each constructor:  c_i : (params) -> (args) -> D params
    ctor_names = []
    ctor_rec_flags = []
    for cname, args in constructors:
        ctor_names.append(cname)
        rec_flags = [a is REC for _, a in args]
        ctor_rec_flags.append(rec_flags)

        arg_tele = []
        for aname, aty in args:
            arg_tele.append((aname, applied if aty is REC else aty))
        ctor_type = _pi(params + arg_tele, applied)
        declare_const(cname, to_debruijn(ctor_type))

    # 3. The recursor:  D.rec : (params) (P) (minors) (x) -> P x
    motive_ty = _pi([("__t", applied)], N.U(motive_univ))  # P : D params -> Type
    rec_tele = list(params) + [("__motive", motive_ty)]

    for ci, (cname, args) in enumerate(constructors):
        minor_tele = []
        ctor_arg_refs = []
        for aname, aty in args:
            if aty is REC:
                minor_tele.append((aname, applied))
                ctor_arg_refs.append(N.Var(aname))
                # induction hypothesis for this recursive argument
                minor_tele.append((f"__ih_{ci}_{aname}",
                                   N.App(N.Var("__motive"), N.Var(aname))))
            else:
                minor_tele.append((aname, aty))
                ctor_arg_refs.append(N.Var(aname))
        ctor_applied = _app_chain(N.Const(cname),
                                  [N.Var(p) for p in param_names] + ctor_arg_refs)
        conclusion = N.App(N.Var("__motive"), ctor_applied)
        rec_tele.append((f"__e{ci}", _pi(minor_tele, conclusion)))

    rec_tele.append(("__x", applied))
    rec_body = N.App(N.Var("__motive"), N.Var("__x"))
    rec_type = _pi(rec_tele, rec_body)

    rec_name = name + ".rec"
    declare_const(rec_name, to_debruijn(rec_type))
    register_recursor(rec_name, name, len(params), ctor_names, ctor_rec_flags)

    if check:
        # Sanity: every generated type must itself type-check to a sort.
        for nm in [name] + ctor_names + [rec_name]:
            from kernel.core import const_type
            s = normalize(infer([], const_type(nm)))
            if not isinstance(s, Univ):
                raise TypeError_(
                    f"generated type of '{nm}' is not a sort: {pretty(const_type(nm))}")

    return rec_name
