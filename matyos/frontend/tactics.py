"""
A small tactic engine (Phase C5a).

Tactics let you write a proof as a *script* that manipulates the goal, instead
of spelling out the raw proof term. Crucially the tactic engine is **untrusted**:
it only *builds* a surface term, which the kernel then type-checks against the
theorem statement. A buggy tactic can at worst fail the kernel check — it can
never certify a false theorem. (This is the de Bruijn criterion at work.)

Supported tactics (C5a):
    intro x [y z ...]   peel function-type binders into named hypotheses
    exact <term>        close the goal with an explicit term (may use hyps)
    assumption          close the goal using a hypothesis whose type matches
    refl                close a reflexive equality goal `Eq A a a`

`apply` with sub-goals needs unification/elaboration (Phase C4) and is the next
tactic milestone.
"""

from matyos.kernel.core import N, to_debruijn, def_equal


class TacticError(Exception):
    pass


def _fold_lam(binders, body):
    result = body
    for name, ty in reversed(binders):
        result = N.Lam(name, ty, result)
    return result


def _rename(node, old, new):
    """Rename free occurrences of binder `old` to `new` in a surface type,
    respecting shadowing."""
    if isinstance(node, N.Var):
        return N.Var(new) if node.name == old else node
    if isinstance(node, (N.Const, N.U, N.Prop)):
        return node
    if isinstance(node, N.Arrow):
        return N.Arrow(_rename(node.domain, old, new), _rename(node.codomain, old, new))
    if isinstance(node, N.App):
        return N.App(_rename(node.func, old, new), _rename(node.arg, old, new))
    if isinstance(node, N.Pi):
        dom = _rename(node.domain, old, new)
        cod = node.codomain if node.name == old else _rename(node.codomain, old, new)
        return N.Pi(node.name, dom, cod)
    if isinstance(node, N.Lam):
        dom = _rename(node.domain, old, new)
        body = node.body if node.name == old else _rename(node.body, old, new)
        return N.Lam(node.name, dom, body)
    return node


def _eq_parts(target):
    """If `target` is `Eq A a b` (surface), return (A, a, b), else None."""
    spine = []
    node = target
    while isinstance(node, N.App):
        spine.append(node.arg)
        node = node.func
    if isinstance(node, N.Const) and node.name == "Eq" and len(spine) == 3:
        b, a, A = spine  # spine collected innermost-arg-last
        return A, a, b
    return None


def run_tactics(goal_surface, tactics):
    """Build a surface proof term for `goal_surface` from a tactic list.
    Raises TacticError on an unsolvable/ill-formed script."""
    binders = []          # [(name, type_surface)] introduced so far
    target = goal_surface

    for tac in tactics:
        op = tac[0]
        if op == "intro":
            for nm in tac[1]:
                if isinstance(target, N.Pi):
                    binders.append((nm, target.domain))
                    target = _rename(target.codomain, target.name, nm)
                elif isinstance(target, N.Arrow):
                    binders.append((nm, target.domain))
                    target = target.codomain
                else:
                    raise TacticError(
                        f"intro {nm}: goal is not a function type")
        elif op == "exact":
            return _fold_lam(binders, tac[1])
        elif op == "assumption":
            scope = [n for n, _ in reversed(binders)]
            tgt = to_debruijn(target, scope)
            for nm, ty in reversed(binders):
                if def_equal(to_debruijn(ty, scope), tgt):
                    return _fold_lam(binders, N.Var(nm))
            raise TacticError("assumption: no hypothesis matches the goal")
        elif op == "refl":
            parts = _eq_parts(target)
            if parts:
                A, a, b = parts
                scope = [n for n, _ in reversed(binders)]
                if def_equal(to_debruijn(a, scope), to_debruijn(b, scope)):
                    return _fold_lam(binders,
                                     N.App(N.App(N.Const("refl"), A), a))
            raise TacticError("refl: goal is not a reflexive equality")
        else:
            raise TacticError(f"unknown tactic: {op}")

    raise TacticError("unsolved goal: script ended without "
                      "exact / assumption / refl")
