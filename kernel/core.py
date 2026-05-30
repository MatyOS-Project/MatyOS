"""
A trusted kernel for a minimal dependent type theory.

This is the *seed* of a real proof assistant -- the same kind of core that sits
at the heart of Lean, Coq and Agda. It implements a predicative dependent type
theory (Martin-Lof / lambda-Pi with a universe hierarchy):

    Univ 0 : Univ 1 : Univ 2 : ...                 (a tower of universes)
    Pi (x : A), B                                  (dependent function types)
    fun (x : A) => b                               (lambda abstraction)
    f a                                            (application)

Via the Curry-Howard correspondence:
    * a PROPOSITION is a TYPE,
    * a PROOF of it is a TERM of that type,
    * "P implies Q" is the (non-dependent) function type  Pi (_ : P), Q,
    * "for all x : A, P x" is the (dependent) function type Pi (x : A), P x.

The kernel's only job -- and the only thing that must be trusted -- is:
given a term, compute its type (`infer`), rejecting anything ill-typed.
If the kernel is sound, a term that type-checks against a proposition-type is a
valid proof of that proposition. Everything else in a proof assistant
(elaboration, tactics, libraries) is untrusted sugar that ultimately produces
terms this kernel checks.

Terms use de Bruijn indices, so alpha-equivalence is syntactic and capture is
handled by explicit shifting. This is the standard, robust representation.

What this seed deliberately does NOT yet have (the road to Lean):
    * inductive types + recursors (Nat, Eq, ...) and termination checking
    * an impredicative Prop and universe polymorphism
    * definitions/delta-reduction, elaboration, implicit args, tactics
Those are the next kernel milestones.
"""

from dataclasses import dataclass
from typing import List


# --------------------------------------------------------------------------
# Terms (de Bruijn).  Var(0) is the nearest enclosing binder.
# --------------------------------------------------------------------------
class Term:
    pass


@dataclass(frozen=True)
class Var(Term):
    index: int


@dataclass(frozen=True)
class Univ(Term):
    level: int  # Univ 0, Univ 1, ...


@dataclass(frozen=True)
class Pi(Term):
    domain: Term       # type of the bound variable (in the outer context)
    codomain: Term     # result type (in the context extended by `domain`)


@dataclass(frozen=True)
class Lam(Term):
    domain: Term       # declared type of the bound variable
    body: Term         # body (in the context extended by `domain`)


@dataclass(frozen=True)
class App(Term):
    func: Term
    arg: Term


class TypeError_(Exception):
    """Raised by the kernel when a term fails to type-check."""


# --------------------------------------------------------------------------
# Shifting and substitution (de Bruijn).  Standard TAPL-style definitions.
# --------------------------------------------------------------------------
def shift(term: Term, d: int, cutoff: int = 0) -> Term:
    """Add `d` to every free variable with index >= cutoff."""
    if isinstance(term, Var):
        return Var(term.index + d) if term.index >= cutoff else term
    if isinstance(term, Univ):
        return term
    if isinstance(term, Pi):
        return Pi(shift(term.domain, d, cutoff),
                  shift(term.codomain, d, cutoff + 1))
    if isinstance(term, Lam):
        return Lam(shift(term.domain, d, cutoff),
                   shift(term.body, d, cutoff + 1))
    if isinstance(term, App):
        return App(shift(term.func, d, cutoff), shift(term.arg, d, cutoff))
    raise TypeError_(f"shift: unknown term {term}")


def subst(term: Term, j: int, s: Term) -> Term:
    """Substitute `s` for the free variable with index `j`."""
    if isinstance(term, Var):
        return s if term.index == j else term
    if isinstance(term, Univ):
        return term
    if isinstance(term, Pi):
        return Pi(subst(term.domain, j, s),
                  subst(term.codomain, j + 1, shift(s, 1, 0)))
    if isinstance(term, Lam):
        return Lam(subst(term.domain, j, s),
                   subst(term.body, j + 1, shift(s, 1, 0)))
    if isinstance(term, App):
        return App(subst(term.func, j, s), subst(term.arg, j, s))
    raise TypeError_(f"subst: unknown term {term}")


def _beta(body: Term, arg: Term) -> Term:
    """Substitute `arg` into a body that lives under one binder, dropping it."""
    return shift(subst(body, 0, shift(arg, 1, 0)), -1, 0)


# --------------------------------------------------------------------------
# Normalization and definitional equality.
# The theory is strongly normalizing, so full beta-normal form is well defined.
# --------------------------------------------------------------------------
def normalize(term: Term) -> Term:
    if isinstance(term, (Var, Univ)):
        return term
    if isinstance(term, Pi):
        return Pi(normalize(term.domain), normalize(term.codomain))
    if isinstance(term, Lam):
        return Lam(normalize(term.domain), normalize(term.body))
    if isinstance(term, App):
        f = normalize(term.func)
        a = normalize(term.arg)
        if isinstance(f, Lam):
            return normalize(_beta(f.body, a))
        return App(f, a)
    raise TypeError_(f"normalize: unknown term {term}")


def def_equal(a: Term, b: Term) -> bool:
    """Definitional equality = equality of normal forms (de Bruijn => no alpha)."""
    return normalize(a) == normalize(b)


# --------------------------------------------------------------------------
# Type inference -- the trusted core.
# Context is a list with ctx[0] = type of the nearest binder (Var 0).
# A stored type is valid in the context that existed when it was pushed, so a
# lookup of Var k shifts it by k+1 into the current context.
# --------------------------------------------------------------------------
def infer(ctx: List[Term], term: Term) -> Term:
    if isinstance(term, Univ):
        return Univ(term.level + 1)

    if isinstance(term, Var):
        if term.index < 0 or term.index >= len(ctx):
            raise TypeError_(f"unbound variable: Var({term.index})")
        return shift(ctx[term.index], term.index + 1, 0)

    if isinstance(term, Pi):
        s_dom = normalize(infer(ctx, term.domain))
        if not isinstance(s_dom, Univ):
            raise TypeError_(f"Pi domain is not a type: {term.domain}")
        s_cod = normalize(infer([term.domain] + ctx, term.codomain))
        if not isinstance(s_cod, Univ):
            raise TypeError_(f"Pi codomain is not a type: {term.codomain}")
        # predicative rule: the product lives in the larger universe
        return Univ(max(s_dom.level, s_cod.level))

    if isinstance(term, Lam):
        s_dom = normalize(infer(ctx, term.domain))
        if not isinstance(s_dom, Univ):
            raise TypeError_(f"lambda domain is not a type: {term.domain}")
        body_ty = infer([term.domain] + ctx, term.body)
        return Pi(term.domain, body_ty)

    if isinstance(term, App):
        fn_ty = normalize(infer(ctx, term.func))
        if not isinstance(fn_ty, Pi):
            raise TypeError_(f"applying a non-function (type {fn_ty})")
        arg_ty = infer(ctx, term.arg)
        if not def_equal(arg_ty, fn_ty.domain):
            raise TypeError_(
                "argument type mismatch:\n"
                f"   expected: {pretty(fn_ty.domain)}\n"
                f"   got     : {pretty(arg_ty)}"
            )
        # the result type is the codomain with the argument substituted in
        return _beta(fn_ty.codomain, term.arg)

    raise TypeError_(f"infer: unknown term {term}")


def type_check(term: Term, expected: Term, ctx: List[Term] = None) -> bool:
    """Check that `term` has (definitionally) the `expected` type."""
    ctx = ctx or []
    actual = infer(ctx, term)
    return def_equal(actual, expected)


# --------------------------------------------------------------------------
# Pretty-printing (named, for readability).  Not trusted; display only.
# --------------------------------------------------------------------------
def pretty(term: Term, names: List[str] = None) -> str:
    names = names or []

    def fresh(prefix="x"):
        return f"{prefix}{len(names)}"

    if isinstance(term, Univ):
        return f"Type{term.level}"
    if isinstance(term, Var):
        if term.index < len(names):
            return names[term.index]
        return f"#{term.index}"
    if isinstance(term, Pi):
        name = fresh()
        dom = pretty(term.domain, names)
        cod = pretty(term.codomain, [name] + names)
        # render non-dependent Pi as an arrow
        if not _occurs(term.codomain, 0):
            return f"({dom} -> {cod})"
        return f"(Pi ({name} : {dom}), {cod})"
    if isinstance(term, Lam):
        name = fresh()
        dom = pretty(term.domain, names)
        body = pretty(term.body, [name] + names)
        return f"(fun ({name} : {dom}) => {body})"
    if isinstance(term, App):
        return f"({pretty(term.func, names)} {pretty(term.arg, names)})"
    return str(term)


def _occurs(term: Term, idx: int) -> bool:
    if isinstance(term, Var):
        return term.index == idx
    if isinstance(term, Univ):
        return False
    if isinstance(term, Pi):
        return _occurs(term.domain, idx) or _occurs(term.codomain, idx + 1)
    if isinstance(term, Lam):
        return _occurs(term.domain, idx) or _occurs(term.body, idx + 1)
    if isinstance(term, App):
        return _occurs(term.func, idx) or _occurs(term.arg, idx)
    return False


# --------------------------------------------------------------------------
# Named surface syntax -> de Bruijn (so examples are readable).
# Also display-only; the kernel still checks the de Bruijn terms.
# --------------------------------------------------------------------------
class N:
    """Named-term builders. Convert with `to_debruijn`."""
    @dataclass(frozen=True)
    class Var:
        name: str

    @dataclass(frozen=True)
    class U:
        level: int

    @dataclass(frozen=True)
    class Pi:
        name: str
        domain: "object"
        codomain: "object"

    @dataclass(frozen=True)
    class Arrow:   # non-dependent function type sugar:  A -> B
        domain: "object"
        codomain: "object"

    @dataclass(frozen=True)
    class Lam:
        name: str
        domain: "object"
        body: "object"

    @dataclass(frozen=True)
    class App:
        func: "object"
        arg: "object"


def to_debruijn(term, scope: List[str] = None) -> Term:
    scope = scope or []
    if isinstance(term, N.U):
        return Univ(term.level)
    if isinstance(term, N.Var):
        if term.name not in scope:
            raise TypeError_(f"unknown name in surface term: {term.name}")
        return Var(scope.index(term.name))  # nearest binding wins
    if isinstance(term, N.Arrow):
        dom = to_debruijn(term.domain, scope)
        cod = to_debruijn(term.codomain, ["_"] + scope)
        return Pi(dom, cod)
    if isinstance(term, N.Pi):
        dom = to_debruijn(term.domain, scope)
        cod = to_debruijn(term.codomain, [term.name] + scope)
        return Pi(dom, cod)
    if isinstance(term, N.Lam):
        dom = to_debruijn(term.domain, scope)
        body = to_debruijn(term.body, [term.name] + scope)
        return Lam(dom, body)
    if isinstance(term, N.App):
        return App(to_debruijn(term.func, scope), to_debruijn(term.arg, scope))
    raise TypeError_(f"to_debruijn: unknown surface term {term}")
