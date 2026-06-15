"""
A metavariable-based tactic engine (Phase C4 / C5b).

The proof state is a *queue of open goals*. Each goal is a metavariable with its
own context and target type; tactics act on the focused (first) goal and may
spawn new sub-goals (e.g. `induction` yields a base case and a step case). The
proof term is a skeleton with `Meta` holes; once every goal is closed, the
skeleton is instantiated to a closed term that the kernel re-checks.

The engine is UNTRUSTED — it only *builds* a term; the kernel decides validity,
so a bug can make a tactic fail but never certify a false theorem.

Tactics: intro · exact · assumption · refl · rewrite · induction.
"""

from dataclasses import dataclass

from matyos.kernel import core
from matyos.kernel.core import (
    N, Term, to_debruijn, infer, normalize, def_equal, shift, _beta, _mk_app,
    const_type, Var, Univ, PropSort, Const, Pi, Lam, App,
)


class TacticError(Exception):
    pass


@dataclass
class Meta(Term):
    id: int


class _Goal:
    __slots__ = ("ctx", "names", "target", "solution")

    def __init__(self, ctx, names, target):
        self.ctx, self.names, self.target, self.solution = ctx, names, target, None


# ----- helpers -----
def _eq_parts(t):
    t = normalize(t)
    spine = []
    while isinstance(t, App):
        spine.append(t.arg)
        t = t.func
    if isinstance(t, Const) and t.name == "Eq" and len(spine) == 3:
        b, a, A = spine
        return A, a, b
    return None


def _abstract(term, a, k=0):
    if def_equal(term, shift(a, k, 0)):
        return Var(k)
    if isinstance(term, Var):
        return Var(term.index + 1) if term.index >= k else term
    if isinstance(term, (Univ, Const, PropSort)):
        return term
    if isinstance(term, Pi):
        return Pi(_abstract(term.domain, a, k), _abstract(term.codomain, a, k + 1))
    if isinstance(term, Lam):
        return Lam(_abstract(term.domain, a, k), _abstract(term.body, a, k + 1))
    if isinstance(term, App):
        return App(_abstract(term.func, a, k), _abstract(term.arg, a, k))
    raise TacticError("rewrite: cannot abstract over this term")


def _transport(A, a, b, P, target_Pa, ht):
    A1, a1 = shift(A, 1, 0), shift(a, 1, 0)
    eq_a_y = App(App(App(Const("Eq"), A1), a1), Var(0))
    P2, a2 = shift(P, 2, 0), shift(a, 2, 0)
    body_pp = Pi(App(P2, Var(1)), shift(App(P2, a2), 1, 0))
    pprime = Lam(A, Lam(eq_a_y, body_pp))
    d = Lam(target_Pa, Var(0))
    return App(App(App(App(App(App(Const("Eq.J"), A), a), pprime), d), b), ht)


def _instantiate(term, metas):
    if isinstance(term, Meta):
        sol = metas[term.id].solution
        if sol is None:
            raise TacticError("internal: unsolved metavariable")
        return _instantiate(sol, metas)
    if isinstance(term, (Var, Univ, PropSort, Const)):
        return term
    if isinstance(term, Pi):
        return Pi(_instantiate(term.domain, metas), _instantiate(term.codomain, metas))
    if isinstance(term, Lam):
        return Lam(_instantiate(term.domain, metas), _instantiate(term.body, metas))
    if isinstance(term, App):
        return App(_instantiate(term.func, metas), _instantiate(term.arg, metas))
    return term


def run_tactics(goal, tactics):
    if not isinstance(goal, Term):
        goal = to_debruijn(goal)

    metas = []

    def new_goal(ctx, names, target):
        metas.append(_Goal(ctx, names, target))
        return len(metas) - 1

    root = new_goal([], [], goal)
    queue = [root]

    for tac in tactics:
        if not queue:
            raise TacticError("no open goals left for tactic " + tac[0])
        gid = queue[0]
        g = metas[gid]
        op = tac[0]

        if op == "intro":
            cur = gid
            for nm in tac[1]:
                gc = metas[cur]
                t = normalize(gc.target)
                if not isinstance(t, Pi):
                    raise TacticError(f"intro {nm}: goal is not a function type")
                child = new_goal([t.domain] + gc.ctx, [nm] + gc.names, t.codomain)
                metas[cur].solution = Lam(t.domain, Meta(child))
                cur = child
            queue[0:1] = [cur]

        elif op == "exact":
            g.solution = to_debruijn(tac[1], g.names)
            queue.pop(0)

        elif op == "assumption":
            found = False
            for i in range(len(g.ctx)):
                if def_equal(shift(g.ctx[i], i + 1, 0), g.target):
                    g.solution = Var(i)
                    queue.pop(0)
                    found = True
                    break
            if not found:
                raise TacticError("assumption: no hypothesis matches the goal")

        elif op == "refl":
            parts = _eq_parts(g.target)
            if parts and def_equal(parts[1], parts[2]):
                g.solution = App(App(Const("refl"), parts[0]), parts[1])
                queue.pop(0)
            else:
                raise TacticError("refl: goal is not a reflexive equality")

        elif op == "rewrite":
            ht = to_debruijn(tac[1], g.names)
            parts = _eq_parts(infer(g.ctx, ht))
            if not parts:
                raise TacticError("rewrite: the hypothesis is not an equality")
            A, a, b = parts
            body = _abstract(g.target, a, 0)
            if not def_equal(_beta(body, a), g.target):
                raise TacticError("rewrite: could not relocate the term to rewrite")
            P = Lam(A, body)
            tr = _transport(A, a, b, P, g.target, ht)
            child = new_goal(g.ctx, g.names, _beta(body, b))
            g.solution = App(tr, Meta(child))
            queue[0:1] = [child]

        elif op == "induction":
            t = normalize(g.target)
            if not isinstance(t, Pi) or not isinstance(normalize(t.domain), Const):
                raise TacticError("induction: goal must be `forall (x : D), ...` "
                                  "for an inductive D (use it before introducing x)")
            A = normalize(t.domain)
            recname = A.name + ".rec"
            if recname not in core._RECURSORS:
                raise TacticError(f"induction: no recursor for {A.name}")
            info = core._RECURSORS[recname]
            if info["num_params"] != 0:
                raise TacticError("induction: parameterised inductives not yet supported")
            n = len(info["ctor_names"])
            P = Lam(A, t.codomain)                     # motive  fun x => B[x]
            # peel the recursor's minor-premise types with the motive substituted
            rt = _beta(const_type(recname).codomain, P)  # skip the motive binder
            minors, tt = [], rt
            for _ in range(n):
                minors.append(tt.domain)
                tt = shift(tt.codomain, -1, 0)         # drop the (unused) e_i binder
            children = [new_goal(g.ctx, g.names, m) for m in minors]
            g.solution = _mk_app(Const(recname), [P] + [Meta(c) for c in children])
            queue[0:1] = children

        else:
            raise TacticError(f"unknown tactic: {op}")

    if queue:
        raise TacticError(f"{len(queue)} unsolved goal(s) remain")
    return _instantiate(Meta(root), metas)
