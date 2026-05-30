# Architecture & trust model

MatyOS follows the **de Bruijn criterion**: correctness rests on a small,
auditable kernel, and everything else is untrusted machinery that must produce
terms the kernel re-checks.

## The trust boundary

```
                 untrusted                          TRUSTED
   ┌───────────────────────────────────┐     ┌──────────────────────┐
   .elk file ──▶ frontend/surface.py ──▶│     │ matyos/kernel/core   │
   LLM output ─▶ (parser → kernel terms)│ ──▶ │  infer / normalize    │ ──▶ ✓ / ✗
   tactics    ─▶ (future)               │     │  (inductive, equality)│
   realistic  ─▶ logic/realistic.py     │     └──────────────────────┘
   └───────────────────────────────────┘
```

Only `matyos/kernel` must be trusted. If the kernel is sound, then any term that
type-checks against a proposition-type *is* a proof of that proposition,
regardless of how it was generated.

## The kernel (`matyos/kernel`)

A predicative dependent type theory (Martin-Löf / λΠ-with-universes), plus an
impredicative `Prop`.

### `core.py`
- **Terms** (de Bruijn indices): `Var`, `Univ(level)`, `PropSort`, `Const(name)`,
  `Pi(domain, codomain)`, `Lam(domain, body)`, `App(func, arg)`.
- **`shift` / `subst`** — capture-avoiding de Bruijn operations.
- **`normalize`** — full β-normalization, δ-unfolding of definitions, and ι
  (recursor) reduction.
- **`def_equal`** — definitional equality = equality of normal forms (α is free
  thanks to de Bruijn).
- **`infer(ctx, term)`** — the type-checker. Sort rules:
  - `Univ i : Univ (i+1)`, `Prop : Type0`.
  - Product (imax): a `Pi` into `Prop` stays in `Prop` (impredicative);
    otherwise it lands in the larger `Type` universe (predicative `max`).
- **Environment** — global `Const`s (inductives, constructors, recursors,
  definitions); `define(name, type, body)` type-checks a body against its
  annotation before admitting it.

### `inductive.py`
`declare_inductive` generates, *as kernel terms*, the types of the type former,
each constructor, and the recursor (with a dependent motive and induction
hypotheses), and registers the recursor's ι-reduction rule. A **strict
positivity** check rejects declarations like `Bad = mk (Bad -> Bad)` that would
make the logic unsound. Termination holds by construction: the only recursion
is via recursors (no general `fix`).

### `equality.py`
Propositional equality `Eq`, its constructor `refl`, and the based **J**
eliminator with rule `J A a P d a (refl) ⟹ d`. `cong` (congruence) is derived
from J. These are currently trusted primitives; a general indexed-inductive
engine that *derives* them is a planned milestone.

## The front-end (`matyos/frontend/surface.py`)

A tokenizer + recursive-descent parser for the `.elk` language that produces
kernel terms (via the named-surface helper `N` and `to_debruijn`). It is
untrusted: its output is always re-checked by the kernel. See
[language.md](language.md).

## The realistic layer (`matyos/logic/realistic.py`)

A self-contained three-valued propositional logic (Kleene and Łukasiewicz) for
reasoning *about* uncertain propositions. By design it sits **outside** the
trusted kernel: the kernel stays classical/constructive and sound, while
`realistic` models conjecture-with-confidence at the meta level.

## Why this shape scales toward Lean

The hard, dangerous parts (soundness) are concentrated in a tiny kernel that can
be audited and, eventually, verified. The large parts (elaboration, tactics, a
mathematics library, an LLM proof-search loop) are *additive* and untrusted —
they make the system more capable without enlarging what must be trusted. This
is exactly the architecture that lets Lean/Coq scale, and it is what makes an
LLM-driven workflow safe: the model can propose anything; only the kernel
decides what is true.
