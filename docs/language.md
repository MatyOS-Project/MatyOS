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

theorem NAME (b1) ... : TYPE              -- state an obligation (no proof yet)
proof NAME := TERM                        -- discharge theorem NAME; kernel-checks TERM
hypothesis NAME : TYPE                    -- an assumed truth (epistemically "realistic")
conjecture NAME : TYPE                    -- same, labelled a conjecture
test NAME : TERM [= TERM]                 -- normalize TERM (and compare to the RHS if given)
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

### The scientific-method commands

These commands separate *stating* a claim from *proving* it and let a file (or a
[project](projects.md)) record what is assumed versus what is certified. They are
what power the project reports.

```
theorem add_zero_right : forall (n : Nat), Eq Nat (add n zero) n
```
`theorem` **states** an obligation and gives it a name, with no proof. Parameters
before the `:` become Π-binders of the statement, exactly as for `def`.

```
proof add_zero_right :=
  fun (n : Nat) => Nat.rec ... n
```
`proof NAME := TERM` **discharges** a previously stated theorem: the kernel infers
the type of `TERM` and checks it is definitionally equal to the theorem's
statement. On success the name becomes a reusable constant. A `proof` for an
unknown theorem, or whose term has the wrong type, is reported as a failure (and
`matyos check` exits non-zero).

```
hypothesis classical : forall (P : Prop), Or P (Not P)
conjecture add_comm  : forall (a b : Nat), Eq Nat (add a b) (add b a)
```
`hypothesis` and `conjecture` introduce an **assumed truth** — trusted for the
sake of argument but flagged as *realistic* (not certified). They behave
identically; the two keywords just document intent. A proof that uses one
(directly, or via a lemma that used one) is still PROVEN but reported as
**conditional** on that assumption — see
[certified vs. conditional](projects.md#certified-vs-conditional-realistic--and-why-it-matters).

```
test add_2_3 : add (succ (succ zero)) (succ (succ (succ zero)))
             = succ (succ (succ (succ (succ zero))))   -- expect 2 + 3 = 5
test whnf_id : (fun (x : Nat) => x) zero               -- just normalize, no RHS
```
`test NAME : TERM [= TERM]` normalizes `TERM`. With an `= RHS`, it normalizes both
sides and reports `[PASS]` if they are equal or `[FAIL]` (a failure) otherwise.
Without an RHS it simply reports the normal form (`[RAN]`).

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

## Tactics — proofs as scripts (`by … qed`)

Instead of writing a raw proof term, a `proof` or `example` body may be a tactic
script that manipulates the goal. The tactic engine is **untrusted**: it only
*builds* a term, which the kernel re-checks against the statement — so a buggy
script can fail, never certify a falsehood.

```
theorem mp : forall (A : Type), forall (B : Type), (A -> B) -> A -> B
proof mp := by
  intro A B f a      -- peel the binders into hypotheses A, B, f, a
  exact f a          -- close the goal with an explicit term
qed
```

Tactics available so far:

| Tactic | Effect |
|--------|--------|
| `intro x [y …]` | peel function-type binders into named hypotheses |
| `exact <term>`  | close the goal with a term (may use the hypotheses) |
| `assumption`    | close the goal using a hypothesis whose type matches it |
| `refl`          | close a reflexive equality goal `Eq A a a` |
| `rewrite <h>`   | given `h : Eq A a b`, replace `a` by `b` in the goal (transported along `h` via the `J` eliminator) |

A block runs `by` … `qed`; it must end by closing the goal (`exact` /
`assumption` / `refl`). The engine builds a typed proof state (goal + context)
and assembles a term the kernel re-checks. `apply` with sub-goals (needs
unification) and `induction` are the next tactics to land. See
[`examples/proofs/tactics.elk`](../examples/proofs/tactics.elk).
