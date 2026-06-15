"""
A typed tactic engine (Phase C5 / C4-rewrite).

A *proof state* is a single goal: a local context `ctx` (kernel types, de Bruijn,
ctx[0] = type of Var 0), the `target` type, and a continuation `build` that maps
a term solving the current target (in `ctx`) to a closed term solving the
ORIGINAL goal. Tactics refine the state; the closer (`exact`/`assumption`/`refl`)
hands its term to `build`.

The engine is UNTRUSTED: it only *constructs* a term, which the kernel then
type-checks against the theorem statement. A bug here can make a tactic fail —
never certify a false theorem (the de Bruijn criterion).

Tactics: intro · exact · assumption · refl · rewrite.
  rewrite h   (h : Eq A a b)  replaces occurrences of `a` in the goal by `b`,
              transporting the proof back along `h` via the J eliminator.
"""

from matyos.kernel.core import (
    N, Term, to_debruijn, infer, normalize, def_equal, shift, _beta,
    Var, Univ, PropSort, Const, Pi, Lam, App,
)


class TacticError(Exception):
    pass


def _eq_parts(t):
    """If `t` normalises to `Eq A a b`, return (A, a, b), else None."""
    t = normalize(t)
    spine = []
    while isinstance(t, App):
        spine.append(t.arg)
        t = t.func
    if isinstance(t, Const) and t.name == "Eq" and len(spine) == 3:
        b, a, A = spine            # spine is innermost-arg-last
        return A, a, b
    return None


def _abstract(term, a, k=0):
    """Replace occurrences of `a` (lifted to depth k) by Var(k), and shift other
    free variables up by one — i.e. abstract `a` out to form a 1-binder body."""
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
    """Build  Eq.J A a P' d b ht : (P b) -> (P a)  for rewriting a -> b.
    P' := fun (y : A) (e : Eq A a y) => (P y) -> (P a);  d := identity on (P a)."""
    A1, a1 = shift(A, 1, 0), shift(a, 1, 0)
    eq_a_y = App(App(App(Const("Eq"), A1), a1), Var(0))      # under binder y
    P2, a2 = shift(P, 2, 0), shift(a, 2, 0)                  # under binders y, e
    p_at_y = App(P2, Var(1))
    p_at_a = App(P2, a2)
    body_pp = Pi(p_at_y, shift(p_at_a, 1, 0))               # (P y) -> (P a)
    pprime = Lam(A, Lam(eq_a_y, body_pp))
    d = Lam(target_Pa, Var(0))                             # (P a) -> (P a)
    jx = Const("Eq.J")
    return App(App(App(App(App(App(jx, A), a), pprime), d), b), ht)


def run_tactics(goal, tactics):
    """Run a tactic script against `goal` (a kernel Term, or surface to convert).
    Returns the closed proof term, or raises TacticError."""
    if not isinstance(goal, Term):
        goal = to_debruijn(goal)

    ctx = []            # ctx[0] = type of Var 0 (innermost)
    names = []          # parallel binder names, names[0] = innermost
    target = goal
    build = lambda p: p   # term solving target in ctx -> closed term for goal

    for tac in tactics:
        op = tac[0]
        if op == "intro":
            for nm in tac[1]:
                t = normalize(target)
                if not isinstance(t, Pi):
                    raise TacticError(f"intro {nm}: goal is not a function type")
                A = t.domain
                ctx = [A] + ctx
                names = [nm] + names
                build = (lambda bld, dom: (lambda p: bld(Lam(dom, p))))(build, A)
                target = t.codomain

        elif op == "exact":
            return build(to_debruijn(tac[1], names))

        elif op == "assumption":
            for i in range(len(ctx)):
                if def_equal(shift(ctx[i], i + 1, 0), target):
                    return build(Var(i))
            raise TacticError("assumption: no hypothesis matches the goal")

        elif op == "refl":
            parts = _eq_parts(target)
            if parts and def_equal(parts[1], parts[2]):
                A, a, _ = parts
                return build(App(App(Const("refl"), A), a))
            raise TacticError("refl: goal is not a reflexive equality")

        elif op == "rewrite":
            ht = to_debruijn(tac[1], names)
            parts = _eq_parts(infer(ctx, ht))
            if not parts:
                raise TacticError("rewrite: the hypothesis is not an equality")
            A, a, b = parts
            body = _abstract(target, a, 0)
            if not def_equal(_beta(body, a), target):
                raise TacticError("rewrite: could not relocate the term to rewrite")
            P = Lam(A, body)
            tr = _transport(A, a, b, P, target, ht)
            build = (lambda bld, t: (lambda p: bld(App(t, p))))(build, tr)
            target = _beta(body, b)

        else:
            raise TacticError(f"unknown tactic: {op}")

    raise TacticError("unsolved goal: script ended without "
                      "exact / assumption / refl")
