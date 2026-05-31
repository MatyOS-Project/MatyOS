<p align="center">
  <img src="assets/logo.png" width="140" alt="MatyOS logo"/>
</p>

<h1 align="center">MatyOS</h1>

<p align="center">
  <strong>A dependently-typed proof assistant, built to be LLM-native.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/tests-233%20passing-brightgreen" alt="tests"/>
  <img src="https://img.shields.io/badge/platforms-win%20%C2%B7%20linux%20%C2%B7%20macos-blue" alt="platforms"/>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="license"/>
  <img src="https://img.shields.io/badge/status-early%20%C2%B7%20sound%20kernel-orange" alt="status"/>
</p>

---

MatyOS is a proof assistant in the tradition of **Lean, Coq and Agda**: you
state theorems as types and prove them by writing terms that a small, trusted
**kernel** checks. Its long-term goal is to be a system that **large language
models can use to do mathematics** — analysis, conjecture, and proof — with
first-class support for *uncertainty* (the `realistic` truth value).

> **Honest status.** This is an early but *sound* core, not yet a Lean
> competitor in capability. What works today: a trusted dependent-type kernel,
> inductive types with recursors, propositional equality, proof by induction,
> strict-positivity checking, definitions, an impredicative `Prop`, a text
> front-end, and a three-valued "realistic" logic — all covered by 233 tests.
> The road to Lean-class mathematics (elaboration, tactics, and above all a
> mathematics library) is mapped honestly in [ROADMAP.md](ROADMAP.md).

## Why another proof assistant?

Lean/Coq/Agda were designed for humans, decades before LLMs. MatyOS is designed
from day one around two bets:

1. **Soundness is sacred.** Every proof — however it is produced, including by
   an LLM — reduces to a term checked by a tiny trusted kernel. Nothing is ever
   "assumed proven".
2. **Uncertainty is first-class.** Real mathematical work (especially an LLM's)
   is full of *plausible-but-unproven* steps. MatyOS treats this rigorously with
   a three-valued logic (`true` / `false` / `realistic`) that lives in an
   epistemic layer *above* the kernel, so conjecture and certainty never get
   confused. See [the `realistic` idea](#the-realistic-idea).

## Install

Download the `matyos` binary for your platform from the
[**Releases**](https://github.com/MatyOS-Project/MatyOS/releases) page.

Then put it on your `PATH` — or let the installer do it for you (it copies the
binary to a per-user location and updates your `PATH`):

```console
:: Windows  (run from the folder containing matyos.exe / this repo)
> powershell -ExecutionPolicy Bypass -File install.ps1

# Linux / macOS
$ bash install-matyos.sh
```

Open a **new terminal**, and the `matyos` command is available everywhere:

```console
$ matyos version
$ matyos check demo.elk          # type-check a proof file
$ matyos help
```

`matyos check` exits `0` when every proof in the file holds and non-zero when
any proof fails, so it drops straight into CI.

> Want to build from source or contribute? See [CONTRIBUTING.md](CONTRIBUTING.md).

## A first proof

Proofs are written in a small, readable language (`.elk`) and checked by the
kernel. Here is arithmetic *from scratch* — declaring the natural numbers,
defining addition, and proving `n + 0 = n` by induction
([`stdlib/arith.elk`](stdlib/arith.elk)):

```
inductive Nat : Type :=
  | zero : Nat
  | succ : Nat -> Nat

def add (m : Nat) (n : Nat) : Nat :=
  Nat.rec (fun (_ : Nat) => Nat) n (fun (k : Nat) (ih : Nat) => succ ih) m

def cong (A : Type) (B : Type) (f : A -> B) (a : A) (b : A) (e : Eq A a b)
    : Eq B (f a) (f b) :=
  Eq.J A a (fun (x : A) (_ : Eq A a x) => Eq B (f a) (f x)) (refl B (f a)) b e

def add_zero_right (n : Nat) : Eq Nat (add n zero) n :=
  Nat.rec (fun (m : Nat) => Eq Nat (add m zero) m)
          (refl Nat zero)
          (fun (k : Nat) (ih : Eq Nat (add k zero) k) =>
              cong Nat Nat succ (add k zero) k ih)
          n

example : forall (n : Nat), Eq Nat (add n zero) n := add_zero_right
```

```console
$ matyos check stdlib/arith.elk
inductive Nat : Type0  (2 constructors)
def add : (Nat -> (Nat -> Nat))
eval ... = (succ (succ (succ (succ (succ zero)))))        -- 2 + 3 = 5
def cong : (Pi (x0 : Type0), ...)
def add_zero_right : (Pi (x0 : Nat), (((Eq Nat) ((add x0) zero)) x0))
example : (Pi (x0 : Nat), (((Eq Nat) ((add x0) zero)) x0))   [QED]
```

## Projects & the scientific method

Real work is bigger than one proof. A **MatyOS project** is a directory that
mirrors the scientific method — *assume* (hypothesis/conjecture) → *state*
(theorem) → *experiment* (test) → *certify* (proof) — and `matyos check` runs the
whole thing and reports the honest status of every claim. Scaffold one and check
it:

```console
$ matyos new my_theory
Created project 'my_theory'.  Try:  matyos check my_theory

$ matyos check my_theory
==========================================================
 MatyOS project: my_theory
==========================================================

theory: theories/arithmetic
  definitions: Nat, add, cong
  hypotheses / conjectures (realistic):
    [CONJ] add_comm : ...commutativity of addition...
  theorems:
    [PROVEN] add_zero_right   (certified)
  tests:
    [PASS] add_2_3
    [PASS] add_0_4
----------------------------------------------------------
 Summary
   theorems   : 1 proven (1 certified, 0 conditional), 0 open
   conjectures: 1 (realistic)
   tests      : 2 passed, 0 failed, 0 ran
   status     : OK  (exit 0)
----------------------------------------------------------
```

The report draws a hard line between **certified** theorems (depend on nothing
unproven) and **conditional / realistic** ones (rest on an open conjecture) — and
that dependency is tracked transitively, so an assumption buried deep in a chain
of lemmas can never launder itself into a certified result. Projects pack into a
single distributable `.matyos` archive (`matyos pack` / `unpack`). Full details:
[docs/projects.md](docs/projects.md).

### Logic is just types (Curry–Howard)

Propositions are types; proofs are programs ([`examples/proofs/curry_howard.elk`](examples/proofs/curry_howard.elk)):

```
def id            (A : Type) (x : A) : A := x                 -- A implies A
def const         (A : Type) (B : Type) (a : A) (b : B) : A := a
def modus_ponens  (A : Type) (B : Type) (f : A -> B) (a : A) : B := f a

example : forall (A : Type), A -> A := id
```

The kernel *rejects* non-proofs: an ill-typed term like `fun (A:Type)(x:A) => x x`
(self-application) does not type-check, so it cannot masquerade as a proof.

## The `realistic` idea

Classical logic forces every proposition to be `true` or `false`. Real
reasoning — and LLM reasoning especially — also needs **"not (yet) known"**.
MatyOS gives this a precise, textbook semantics (Kleene **K3** and Łukasiewicz
**Ł3** three-valued logics):

| formula | classical | with a `realistic` atom |
|---|---|---|
| `P \/ ~P`  (excluded middle) | valid | **not valid** — undetermined when `P` is `realistic` |
| `~(P /\ ~P)`  (non-contradiction) | valid | **not valid** |
| `P -> P`  (self-implication) | valid | not valid in Kleene · valid in Łukasiewicz |

The failure of excluded middle for a `realistic` atom is the *point*: an
uncertain proposition is neither affirmed nor denied. Crucially, `realistic`
lives **above** the trusted kernel — conjectures carry evidence/confidence and a
status (`conjectured → certified / refuted`), and the kernel only ever certifies
real proofs. This is the intended bridge between informal LLM reasoning and
formal verification (see Realistic track R0–R3 in [ROADMAP.md](ROADMAP.md)).

## Architecture

```
matyos/             the proof assistant
├── kernel/         the TRUSTED core — small and auditable
│   ├── core        terms, normalization, definitional equality, type inference
│   ├── inductive   inductive types, recursors, iota-reduction, strict positivity
│   └── equality    propositional equality (Eq) + the J eliminator
├── frontend/       tokenizer + parser for the .elk proof language
├── logic/          three-valued ("realistic") logic
└── cli             the `matyos` command

stdlib/             standard library, written in MatyOS itself (.elk)
examples/           example proofs (.elk)
docs/               design + language reference
ROADMAP.md          the honest, phased plan toward a Lean-class system
```

**Trust boundary:** only the **kernel** must be trusted. The parser, the
standard library, the `realistic` layer, and any future tactics or LLM output
all ultimately produce terms that the kernel re-checks. If the kernel is sound,
a term that type-checks against a proposition *is* a proof of it.

## Documentation

- [ROADMAP.md](ROADMAP.md) — phased plan and current status (honest about scale)
- [docs/architecture.md](docs/architecture.md) — design and trust model
- [docs/language.md](docs/language.md) — the `.elk` language reference
- [docs/projects.md](docs/projects.md) — projects, the scientific-method workflow, and the `.matyos` archive
- [CONTRIBUTING.md](CONTRIBUTING.md) — building from source, running tests
- [docs/legacy-el-language.md](docs/legacy-el-language.md) — the project's original imperative language

## License

MIT. See [LICENSE](LICENSE).
