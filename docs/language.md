# The `.elk` proof language

A small dependently-typed language. Files are checked with:

```bash
python -m matyos check path/to/file.elk
```

The prelude (propositional equality `Eq`, `refl`, `Eq.J`) is available in every
file automatically.

## Terms

| Syntax | Meaning |
|---|---|
| `x`, `Nat`, `Nat.rec` | variable / global constant (identifiers may contain `.`) |
| `Type`, `Type 3` | a universe (`Type` = `Type 0`) |
| `Prop` | the sort of propositions (impredicative) |
| `f a b` | application (left-associative) |
| `A -> B` | non-dependent function type |
| `(x : A) -> B` | dependent function type (Π) |
| `forall (x : A), B` | same as `(x : A) -> B` |
| `fun (x : A) => e` | lambda abstraction |
| `(e)` | grouping |

Binders may group names: `(x y : A)` binds both `x` and `y` at type `A`.
Comments start with `--` and run to end of line.

## Commands

```
def NAME (b1) (b2) ... : TYPE := TERM     -- a checked definition (function, value, or theorem)
axiom NAME : TYPE                         -- assume a constant of a type (use sparingly!)
inductive NAME (params) : Type[u] :=      -- declare a datatype; auto-derives NAME.rec
    | C1 : T1
    | C2 : T2
example : TYPE := TERM                    -- check an anonymous proof; prints [QED] or [FAIL]
check TERM                                -- print the inferred type of TERM
eval  TERM                                -- print the normal form of TERM
```

### `def`
Parameters before the `:` become both Π-binders of the type and λ-binders of the
body. A **theorem is just a `def`** whose type is a proposition and whose body is
a proof; `def` refuses anything that does not type-check.

### `inductive`
Declares a datatype in `Type u` (Prop-valued inductives are not yet supported in
surface syntax). The recursor `NAME.rec` is generated automatically with the
standard dependent elimination rule and computes by ι-reduction. A constructor
argument whose type is the inductive applied to its parameters is recognized as
*recursive* (so it gets an induction hypothesis in the recursor).

```
inductive Nat : Type :=
  | zero : Nat
  | succ : Nat -> Nat
-- generates  Nat.rec : (P : Nat -> Type) -> P zero
--                    -> ((k : Nat) -> P k -> P (succ k)) -> (n : Nat) -> P n
```

## Worked examples

- [`stdlib/arith.elk`](../stdlib/arith.elk) — `Nat`, `add`, and `n + 0 = n` by induction
- [`stdlib/bool.elk`](../stdlib/bool.elk) — `Bool`, `not`, `and`, `or` with `eval`
- [`stdlib/logic.elk`](../stdlib/logic.elk) — `False`, `Not`, `absurd` in `Prop`
- [`examples/proofs/curry_howard.elk`](../examples/proofs/curry_howard.elk) — combinators as logical theorems

## Notes / limitations (see ROADMAP.md)

- No implicit arguments yet — every type argument is written explicitly
  (elaboration is Phase C4).
- No tactic language yet — proofs are written as raw terms (Phase C5).
- Universe levels are explicit and monomorphic (no universe polymorphism yet).
- Indexed inductives (like `Eq`) are provided as kernel primitives rather than
  declared in surface syntax.
