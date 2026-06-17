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


# ----- metavariable-aware term ops (Meta is opaque: passes through) -----
def _shift(t, d, c=0):
    if isinstance(t, Meta):
        return t
    if isinstance(t, Var):
        return Var(t.index + d) if t.index >= c else t
    if isinstance(t, (Univ, Const, PropSort)):
        return t
    if isinstance(t, Pi):
        return Pi(_shift(t.domain, d, c), _shift(t.codomain, d, c + 1))
    if isinstance(t, Lam):
        return Lam(_shift(t.domain, d, c), _shift(t.body, d, c + 1))
    if isinstance(t, App):
        return App(_shift(t.func, d, c), _shift(t.arg, d, c))
    raise TacticError("apply: cannot shift this term")


def _msubst(t, j, s):
    if isinstance(t, Meta):
        return t
    if isinstance(t, Var):
        return s if t.index == j else t
    if isinstance(t, (Univ, Const, PropSort)):
        return t
    if isinstance(t, Pi):
        return Pi(_msubst(t.domain, j, s), _msubst(t.codomain, j + 1, _shift(s, 1, 0)))
    if isinstance(t, Lam):
        return Lam(_msubst(t.domain, j, s), _msubst(t.body, j + 1, _shift(s, 1, 0)))
    if isinstance(t, App):
        return App(_msubst(t.func, j, s), _msubst(t.arg, j, s))
    raise TacticError("apply: cannot substitute this term")


def _mbeta(body, arg):
    return _shift(_msubst(body, 0, _shift(arg, 1, 0)), -1, 0)


def _has_meta(t):
    if isinstance(t, Meta):
        return True
    if isinstance(t, (Pi, Lam)):
        return _has_meta(t.domain) or _has_meta(t.codomain if isinstance(t, Pi) else t.body)
    if isinstance(t, App):
        return _has_meta(t.func) or _has_meta(t.arg)
    return False


def _match(pat, term, subst):
    """First-order match: `pat` may contain Metas (as leaves), `term` is ground.
    Binds metas in `subst`; returns True on success."""
    while isinstance(pat, Meta) and pat.id in subst:
        pat = subst[pat.id]
    if isinstance(pat, Meta):
        subst[pat.id] = term
        return True
    if isinstance(pat, App) and isinstance(term, App):
        return _match(pat.func, term.func, subst) and _match(pat.arg, term.arg, subst)
    if isinstance(pat, Const) and isinstance(term, Const):
        return pat.name == term.name
    if isinstance(pat, Var) and isinstance(term, Var):
        return pat.index == term.index
    if isinstance(pat, Univ) and isinstance(term, Univ):
        return pat.level == term.level
    if isinstance(pat, PropSort) and isinstance(term, PropSort):
        return True
    if isinstance(pat, Pi) and isinstance(term, Pi):
        return (_match(pat.domain, term.domain, subst)
                and _match(pat.codomain, term.codomain, subst))
    if isinstance(pat, Lam) and isinstance(term, Lam):
        return (_match(pat.domain, term.domain, subst)
                and _match(pat.body, term.body, subst))
    if not _has_meta(pat):
        return def_equal(pat, term)
    return False


def _inst(t, subst):
    """Substitute solved metavariables (a dict id -> term) throughout `t`."""
    if isinstance(t, Meta):
        return _inst(subst[t.id], subst) if t.id in subst else t
    if isinstance(t, (Var, Univ, Const, PropSort)):
        return t
    if isinstance(t, Pi):
        return Pi(_inst(t.domain, subst), _inst(t.codomain, subst))
    if isinstance(t, Lam):
        return Lam(_inst(t.domain, subst), _inst(t.body, subst))
    if isinstance(t, App):
        return App(_inst(t.func, subst), _inst(t.arg, subst))
    return t


class _NoProof(Exception):
    pass


def _auto(ctx, target, depth):
    """Search for a closed term proving `target` in `ctx`. Tries refl,
    assumption, intro, and applying each hypothesis (premises solved
    recursively). Raises _NoProof if nothing is found within `depth`."""
    tn = normalize(target)
    parts = _eq_parts(tn)
    if parts and def_equal(parts[1], parts[2]):
        return App(App(Const("refl"), parts[0]), parts[1])
    for i in range(len(ctx)):
        if def_equal(shift(ctx[i], i + 1, 0), target):
            return Var(i)
    if isinstance(tn, Pi):
        try:
            return Lam(tn.domain, _auto([tn.domain] + ctx, tn.codomain, depth))
        except _NoProof:
            pass
    if depth <= 0:
        raise _NoProof
    for i in range(len(ctx)):
        try:
            return _auto_apply(Var(i), normalize(shift(ctx[i], i + 1, 0)),
                               ctx, target, depth)
        except _NoProof:
            continue
    raise _NoProof


def _auto_apply(head, hty, ctx, target, depth):
    rest, arg_metas, arg_types, mid = hty, [], [], 0
    while isinstance(rest, Pi):
        m = Meta(mid)
        mid += 1
        arg_metas.append(m)
        arg_types.append(rest.domain)         # earlier metas already substituted
        rest = _mbeta(rest.codomain, m)
    subst = {}
    if not arg_metas or not _match(rest, normalize(target), subst):
        raise _NoProof
    args = []
    for k, m in enumerate(arg_metas):
        if m.id in subst:
            args.append(subst[m.id])
        else:
            aty = _inst(arg_types[k], subst)
            if _has_meta(aty):
                raise _NoProof                  # undetermined argument; give up
            term = _auto(ctx, aty, depth - 1)
            subst[m.id] = term
            args.append(term)
    return _mk_app(head, args)


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

        elif op == "auto":
            try:
                g.solution = _auto(g.ctx, g.target, 6)
                queue.pop(0)
            except _NoProof:
                raise TacticError("auto: could not find a proof")

        elif op == "apply":
            ft = to_debruijn(tac[1], g.names)
            rest = normalize(infer(g.ctx, ft))
            arg_ids = []
            while isinstance(rest, Pi):
                child = new_goal(g.ctx, g.names, rest.domain)
                arg_ids.append(child)
                rest = _mbeta(rest.codomain, Meta(child))
            subst = {}
            if not _match(rest, normalize(g.target), subst):
                raise TacticError("apply: the lemma's conclusion does not "
                                  "match the goal")
            for mid in arg_ids:
                if mid in subst:
                    metas[mid].solution = subst[mid]
            opened = [mid for mid in arg_ids if mid not in subst]
            g.solution = _mk_app(ft, [Meta(mid) for mid in arg_ids])
            queue[0:1] = opened

        else:
            raise TacticError(f"unknown tactic: {op}")

    if queue:
        raise TacticError(f"{len(queue)} unsolved goal(s) remain")
    return _instantiate(Meta(root), metas)
