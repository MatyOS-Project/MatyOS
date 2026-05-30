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


@dataclass(frozen=True)
class Const(Term):
    """Reference to a global declaration (an inductive type, a constructor, a
    recursor, or a definition) held in the environment. Closed (no free vars)."""
    name: str


class TypeError_(Exception):
    """Raised by the kernel when a term fails to type-check."""


class PositivityError(TypeError_):
    """Raised when an inductive declaration is not strictly positive (which
    would make the logic unsound / non-terminating)."""


# --------------------------------------------------------------------------
# Global environment.  Inductive types, constructors, recursors and
# definitions are registered here by `kernel/inductive.py`. The kernel trusts
# the *types* recorded here and the recursor reduction rules (the standard
# iota rules); everything else still reduces to terms `infer` checks.
# --------------------------------------------------------------------------
_GLOBALS = {}      # name -> {"type": Term, "value": Term|None}
_RECURSORS = {}    # recursor name -> reduction metadata (see register_recursor)
_REDUCERS = {}     # const name -> fn(spine_args) -> contractum | None (custom iota)


def register_reducer(name, fn):
    """Register a custom reduction rule for a primitive eliminator (e.g. the J
    rule for equality), which does not fit the generic recursor scheme."""
    _REDUCERS[name] = fn


def declare_const(name, type_, value=None):
    _GLOBALS[name] = {"type": type_, "value": value}


def register_recursor(name, inductive, num_params, ctor_names, ctor_rec_flags):
    """Record how a recursor computes.

    inductive       : name of the inductive type it eliminates
    num_params       : number of leading parameters
    ctor_names       : constructor names, in declaration order
    ctor_rec_flags   : per constructor, a list of booleans flagging which of
                       that constructor's value-arguments are recursive.
    """
    _RECURSORS[name] = {
        "inductive": inductive,
        "num_params": num_params,
        "ctor_names": list(ctor_names),
        "ctor_rec_flags": [list(f) for f in ctor_rec_flags],
    }


def const_type(name):
    if name not in _GLOBALS:
        raise TypeError_(f"unknown global constant: {name}")
    return _GLOBALS[name]["type"]


def _spine(term):
    """Unwind an application: f a b c -> (f, [a, b, c])."""
    args = []
    while isinstance(term, App):
        args.append(term.arg)
        term = term.func
    args.reverse()
    return term, args


def _mk_app(head, args):
    for a in args:
        head = App(head, a)
    return head


# --------------------------------------------------------------------------
# Shifting and substitution (de Bruijn).  Standard TAPL-style definitions.
# --------------------------------------------------------------------------
def shift(term: Term, d: int, cutoff: int = 0) -> Term:
    """Add `d` to every free variable with index >= cutoff."""
    if isinstance(term, Var):
        return Var(term.index + d) if term.index >= cutoff else term
    if isinstance(term, (Univ, Const)):
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
    if isinstance(term, (Univ, Const)):
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
    if isinstance(term, Const):
        # delta-reduction: unfold a definition (constructors/recursors/
        # inductives carry no value and stay folded).
        entry = _GLOBALS.get(term.name)
        if entry is not None and entry.get("value") is not None:
            return normalize(entry["value"])
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
        reduced = _try_iota(App(f, a))
        if reduced is not None:
            return normalize(reduced)
        reduced = _try_reducer(App(f, a))
        if reduced is not None:
            return normalize(reduced)
        return App(f, a)
    raise TypeError_(f"normalize: unknown term {term}")


def _try_reducer(term: Term):
    """Fire a custom-registered eliminator reduction (e.g. the J rule)."""
    head, args = _spine(term)
    if isinstance(head, Const) and head.name in _REDUCERS:
        return _REDUCERS[head.name](args)
    return None


def _try_iota(term: Term):
    """Fire a recursor (iota) reduction if `term` is a recursor applied to a
    constructor in scrutinee position. Returns the contractum, or None.

        D.rec params P minors... (c_i cargs...)
            ==>  minor_i  cargs... interleaved with recursive calls

    For each recursive argument a of the constructor, the induction hypothesis
    `D.rec params P minors... a` is passed right after a.
    """
    head, args = _spine(term)
    if not isinstance(head, Const) or head.name not in _RECURSORS:
        return None
    info = _RECURSORS[head.name]
    p = info["num_params"]
    n = len(info["ctor_names"])
    expected = p + 1 + n + 1  # params, motive, minors, scrutinee
    if len(args) < expected:
        return None

    scrutinee = args[p + 1 + n]
    c_head, c_args = _spine(scrutinee)
    if not isinstance(c_head, Const) or c_head.name not in info["ctor_names"]:
        return None

    i = info["ctor_names"].index(c_head.name)
    minor = args[p + 1 + i]
    fixed = args[: p + 1 + n]            # params + motive + minors (for the IH)
    ctor_value_args = c_args[p:]         # drop the constructor's parameter args
    rec_flags = info["ctor_rec_flags"][i]

    result = minor
    for arg, is_rec in zip(ctor_value_args, rec_flags):
        result = App(result, arg)
        if is_rec:
            ih = _mk_app(head, fixed + [arg])
            result = App(result, ih)

    # carry along any arguments applied beyond the scrutinee
    for extra in args[expected:]:
        result = App(result, extra)
    return result


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

    if isinstance(term, Const):
        return const_type(term.name)  # closed: valid in any context

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


def define(name: str, type_term: Term, value_term: Term):
    """Register a checked global definition: verify `value : type`, then store
    it so that `Const(name)` delta-reduces to `value`.

    The declared type is itself verified to be a well-formed type, and the body
    is checked against it -- so a definition can never introduce an ill-typed
    or mis-annotated term into the environment."""
    sort = normalize(infer([], type_term))
    if not isinstance(sort, Univ):
        raise TypeError_(f"definition '{name}': annotation is not a type")
    body_ty = infer([], value_term)
    if not def_equal(body_ty, type_term):
        raise TypeError_(
            f"definition '{name}': body has type {pretty(body_ty)}, "
            f"but was annotated {pretty(type_term)}")
    declare_const(name, type_term, value_term)
    return Const(name)


# --------------------------------------------------------------------------
# Pretty-printing (named, for readability).  Not trusted; display only.
# --------------------------------------------------------------------------
def pretty(term: Term, names: List[str] = None) -> str:
    names = names or []

    def fresh(prefix="x"):
        return f"{prefix}{len(names)}"

    if isinstance(term, Univ):
        return f"Type{term.level}"
    if isinstance(term, Const):
        return term.name
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
    if isinstance(term, (Univ, Const)):
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

    @dataclass(frozen=True)
    class Const:
        name: str


def to_debruijn(term, scope: List[str] = None) -> Term:
    scope = scope or []
    if isinstance(term, Term):
        return term  # already a kernel term (allows embedding)
    if isinstance(term, N.Const):
        return Const(term.name)
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
