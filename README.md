<p align="center">
  <img src="assets/logo.png" width="140" alt="MatyOS logo"/>
</p>

<h1 align="center">MatyOS</h1>

<p align="center">
  <strong>A dependently-typed proof assistant, built to be LLM-native.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/tests-233%20passing-brightgreen" alt="tests"/>
  <img src="https://img.shields.io/badge/python-3.8%2B-blue" alt="python"/>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="license"/>
  <img src="https://img.shields.io/badge/status-early%20%C2%B7%20sound%20kernel-orange" alt="status"/>
</p>

---

MatyOS is a proof assistant in the tradition of **Lean, Coq and Agda**: you
state theorems as types and prove them by writing terms that a small, trusted
**kernel** type-checks. Its long-term goal is to be a system that **large
language models can use to do mathematics** — analysis, conjecture, and proof —
with first-class support for *uncertainty* (the `realistic` truth value).

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
   an LLM — reduces to a term checked by a tiny trusted kernel (`matyos/kernel`).
   Nothing is ever "assumed proven".
2. **Uncertainty is first-class.** Real mathematical work (especially an LLM's)
   is full of *plausible-but-unproven* steps. MatyOS treats this rigorously with
   a three-valued logic (`true` / `false` / `realistic`) that lives in an
   epistemic layer *above* the kernel, so conjecture and certainty never get
   confused. See [the `realistic` idea](#the-realistic-idea).

## Install & run

**Build the standalone `matyos` binary** (then nothing else is required to run it):

```bash
pip install pyinstaller     # one-time, build dependency only
python build_matyos.py      # produces dist/matyos  (matyos.exe on Windows)
```

**Or install the `matyos` command via pip** (needs Python on the user's machine):

```bash
pip install -e .            # puts `matyos` on your PATH
```

Either way you then use the language through its own command:

```bash
matyos check stdlib/arith.elk      # type-check a proof file (exit 0 = all proofs hold)
matyos check stdlib/bool.elk
matyos version
matyos help
```

`matyos check` exits non-zero if any proof fails, so it drops straight into CI.

## A first proof

Proofs are written in a small, readable language and checked by the kernel.
Here is arithmetic *from scratch* — declaring the natural numbers, defining
addition, and proving `n + 0 = n` by induction
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

```text
$ matyos check stdlib/arith.elk
inductive Nat : Type0  (2 constructors)
def add : (Nat -> (Nat -> Nat))
eval ... = (succ (succ (succ (succ (succ zero)))))        -- 2 + 3 = 5
def cong : (Pi (x0 : Type0), ...)
def add_zero_right : (Pi (x0 : Nat), (((Eq Nat) ((add x0) zero)) x0))
example : (Pi (x0 : Nat), (((Eq Nat) ((add x0) zero)) x0))   [QED]
```

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
**Ł3** three-valued logics) in [`matyos/logic/realistic.py`](matyos/logic/realistic.py):

```text
$ python -m matyos.logic.realistic
   excluded middle  P \/ ~P     : not valid   (P=realistic -> realistic)
   self-implication P -> P      : not valid (Kleene) / VALID (Lukasiewicz)
```

The failure of excluded middle for a `realistic` atom is the *point*: an
uncertain proposition is neither affirmed nor denied. Crucially, `realistic`
lives **above** the trusted kernel — conjectures carry evidence/confidence and a
status (`conjectured → certified / refuted`), and the kernel only ever certifies
real proofs. This is the intended bridge between informal LLM reasoning and
formal verification (see Realistic track R0–R3 in [ROADMAP.md](ROADMAP.md)).

## Architecture

```
matyos/                 # the proof assistant (Python package)
├── kernel/             #   the TRUSTED core — keep this small and correct
│   ├── core.py         #     terms, normalization, definitional equality, infer
│   ├── inductive.py    #     inductive types, recursors, iota-reduction, positivity
│   └── equality.py     #     propositional equality (Eq) + the J eliminator
├── frontend/
│   └── surface.py      #   tokenizer + parser for the .elk proof language
├── logic/
│   └── realistic.py    #   three-valued (Kleene / Lukasiewicz) "realistic" logic
├── cli.py              #   the `matyos` command (check / eval / version)
└── __main__.py         #   enables `python -m matyos` too

stdlib/                 # standard library, written in the proof language (.elk)
examples/proofs/        # example proofs (.elk)
tests/                  # pytest suite (233 tests)
docs/                   # design + language documentation
ROADMAP.md              # the honest, phased plan toward a Lean-class system

compiler/ utils/ system/ examples/*.el   # legacy imperative "El" language
                                          # (see docs/legacy-el-language.md)
```

**Trust boundary:** only `matyos/kernel` must be trusted. The parser, the
standard library, the `realistic` layer, and any future tactics or LLM output
all ultimately produce terms that the kernel re-checks.

## Development & testing

```bash
python -m pytest -q          # 233 tests
python -m pytest tests/test_kernel_core.py tests/test_inductive.py -q
```

The suite covers the kernel (substitution/normalization/inference, sort rules),
inductive types and computation, the J rule and the `n+0=n` induction proof,
strict-positivity rejection, definitions, impredicative `Prop`, the surface
parser, end-to-end checking of every `.elk` file, and the three-valued logic.

## Documentation

- [ROADMAP.md](ROADMAP.md) — phased plan and current status (honest about scale)
- [docs/architecture.md](docs/architecture.md) — design and trust model
- [docs/language.md](docs/language.md) — the `.elk` language reference
- [docs/legacy-el-language.md](docs/legacy-el-language.md) — the original imperative language

## License

MIT. See [LICENSE](LICENSE).
