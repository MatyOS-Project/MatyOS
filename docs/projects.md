# MatyOS projects & the scientific method

A single `.elk` file is fine for one proof. Real mathematical work is bigger: you
*assume* some things, you *state* what you want to show, you *experiment*, and only
then do you *prove*. A **MatyOS project** is a directory that mirrors this
scientific method as a file system, and `matyos check` runs the whole thing
through one shared kernel session and reports the epistemic status of every claim.

## The workflow

```
hypothesis  ─►  theorem  ─►  test  ─►  proof  ─►  theory
 (assume)       (state)     (probe)   (certify)   (verified body)
```

1. **Hypothesis / conjecture** — write down what you are *assuming* is true but
   have not proved. These are epistemically **realistic**: trusted for the sake
   of argument, but flagged so nothing built on them is mistaken for certainty.
2. **Theorem** — state the proposition you intend to establish. A theorem on its
   own is just an *open obligation*; it carries no proof yet.
3. **Test** — run computational experiments. The kernel normalizes expressions
   and checks them against expected results, the way a scientist probes a claim
   before committing to a proof.
4. **Proof** — supply a term and let the **trusted kernel** check it against the
   stated theorem. If it checks, the theorem is discharged.
5. **Theory** — the accumulated, verified body of knowledge: the definitions,
   theorems, and proofs grouped together in a sub-directory.

## File types

A project is a "sigma of files" — each file plays one role, identified purely by
its extension:

| Extension | Role | Holds |
|---|---|---|
| `.elk`  | definitions & datatypes | the shared vocabulary (`inductive`, `def`) |
| `.hyp`  | hypotheses / conjectures | assumed truths (`hypothesis`, `conjecture`) |
| `.thm`  | theorem statements | the propositions you aim to establish (`theorem`) |
| `.test` | tests / experiments | computational checks (`test`) |
| `.prf`  | proofs | kernel-checked derivations (`proof`) |

`matyos check` always runs files in **scientific-method order** regardless of how
they sit on disk: definitions first, then hypotheses, then theorems, then tests,
then proofs. So a proof can always refer to a theorem stated in another file, and
a definition is in scope everywhere. (See [docs/language.md](language.md) for the
syntax of each command.)

## What is a "theory"?

A **theory** is simply a sub-directory that groups related files. Everything
under `theories/arithmetic/` belongs to the *arithmetic* theory; the report
groups its definitions, conjectures, theorems, and tests together under that
heading. A project can hold many theories side by side.

## The `.matyos` archive

A whole project packs into a single **`.matyos`** file — a zip archive that is
the project's distributable form. You can hand someone a `.matyos`, and
`matyos check` will verify it directly without unpacking it first:

```console
$ matyos pack my_theory          # my_theory/  ->  my_theory.matyos
$ matyos check my_theory.matyos  # verify the archive as-is
$ matyos unpack my_theory.matyos # extract it back to a directory
```

## Certified vs. conditional (realistic) — and why it matters

Every proven theorem carries one of two honesty labels:

- **PROVEN (certified)** — the proof term reduces, through the trusted kernel, to
  a derivation that depends on *no* conjecture or hypothesis. This is unconditional
  mathematical truth.
- **PROVEN (conditional)** — the proof checks, but it *uses* an open conjecture or
  hypothesis somewhere. The theorem is true **if** those assumptions are. The
  report names exactly which assumptions it rests on.

The crucial part is that conditionality is **transitive**. If lemma `B` is proved
using conjecture `C`, then `B` is conditional on `C`. If theorem `A` is then proved
using `B` — even without mentioning `C` directly — `A` is *still* conditional on
`C`. MatyOS tracks this dependency chain automatically, so an assumption buried
three lemmas deep can never quietly launder itself into a "certified" result.

This is what makes the system honest for LLM-driven mathematics: an assistant can
freely conjecture and build on its conjectures, but the final report draws a hard
line between what has been *certified* and what is merely *realistic* (conditional
on unproven assumptions).

## The CLI

| Command | What it does |
|---|---|
| `matyos new <name>`        | scaffold a new project with a sample theory |
| `matyos check <path>`      | check a `.elk` file, a project directory, or a `.matyos` archive |
| `matyos pack <dir> [out]`  | pack a project directory into a `.matyos` archive |
| `matyos unpack <file> [dir]` | extract a `.matyos` archive |

`matyos check` exits `0` when every proof holds and every test passes, and
non-zero otherwise — so it drops straight into CI.

## A walkthrough: `matyos new`

Scaffold a fresh project:

```console
$ matyos new my_theory
Created project 'my_theory'.  Try:  matyos check my_theory
```

This lays out a small arithmetic theory:

```
my_theory/
├── matyos.toml                       # project manifest (name, version)
└── theories/
    └── arithmetic/
        ├── defs.elk                  # Nat, add, cong   (the vocabulary)
        ├── conjectures.hyp           # add_comm         (an OPEN conjecture)
        ├── nat.thm                   # add_zero_right   (the obligation)
        ├── nat.test                  # add_2_3, add_0_4 (experiments)
        └── nat.prf                   # the proof of add_zero_right
```

The sample proves **`add_zero_right`** (`n + 0 = n`) by induction — a *certified*
result — while leaving **`add_comm`** (commutativity of addition) as an open
conjecture, plus two passing tests. Now check it:

```console
$ matyos check my_theory
==========================================================
 MatyOS project: my_theory
==========================================================

theory: theories/arithmetic
  definitions: Nat, add, cong
  hypotheses / conjectures (realistic):
    [CONJ] add_comm : (Pi (x0 : Nat), (Pi (x1 : Nat), (((Eq Nat) ((add x0) x1)) ((add x1) x0))))
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

Read the report top to bottom and you see the scientific method laid out: the
shared **definitions**, the open **conjecture** (`add_comm`, realistic), the
**theorem** that was discharged (`add_zero_right`, certified), and the **tests**
that passed. The summary tallies it all and reports a clean `OK` (exit `0`).

To watch conditionality in action, write a `.prf` whose term uses `add_comm`: its
theorem will report `[PROVEN] ... (conditional on: add_comm)` instead of
`certified`, and any later theorem that uses *it* will inherit the same condition.

## See also

- [docs/language.md](language.md) — the `theorem` / `proof` / `hypothesis` /
  `conjecture` / `test` commands and the full `.elk` term syntax.
- [README.md](../README.md) — the `realistic` idea and the trust boundary.

## Sealing a completed theory into a `.matyos` archive

When a project is **complete** — every theorem proven and no test failing (open
*conjectures* are allowed; they are deliberately realistic) — seal it into a
single compressed `.matyos` archive with `matyos build`:

```console
$ matyos build my_theory
sealed -> my_theory.matyos  (1 certified, 0 conditional, 0 open)
```

`matyos build` refuses to seal an incomplete project (open theorems or failed
checks) and exits non-zero; pass `--force` to archive anyway (the manifest then
records `completed: false`).

A `.matyos` is a compressed (zip/DEFLATE) bundle — a *sigma of files* — of every
source file **plus**:

- `MANIFEST.json` — a machine-readable table of contents and status (theories,
  each theorem's certified/conditional/open status and its conjecture
  dependencies, tests, and a summary). This makes the archive self-describing.
- `REPORT.txt` — the human-readable status report.

Inspect a sealed archive without re-running the kernel:

```console
$ matyos info my_theory.matyos
my_theory  (MatyOS 0.5.0, built 2026-05-31T01:04:30Z)
  completed : True
  theorems  : 1 proven (1 certified, 0 conditional), 0 open
  conjectures: 1 (realistic)
```

`matyos check my_theory.matyos` re-verifies the archive from source (it never
trusts the embedded manifest) — `info` is the quick read, `check` is the proof.

## File types & icons

Each MatyOS file type has a black-and-white icon (see
[`assets/icons`](../assets/icons)):

| Icon | Extension | Role |
|------|-----------|------|
| `Σ` | `.matyos` | sealed project archive (a *sigma of files*) |
| `∀` | `.thm`  | theorem statement |
| `∎` | `.prf`  | proof (kernel-checked) |
| `∃` | `.hyp`  | hypothesis / conjecture (realistic) |
| `✓` | `.test` | test / experiment |
| `λ` | `.elk`  | definitions & datatypes |

## Machine-readable output (`--json`) — for tools & LLMs

Add `--json` to `matyos check` to get a structured result instead of pretty
text — the same facts the kernel sees, ready for CI, tooling, or an LLM loop:

```console
$ matyos check --json my_theory          # a project -> the full MANIFEST as JSON
$ matyos check --json proof.elk           # a file -> { failures, events: [...] }
```

For a project it emits the manifest (theories, each theorem's
`status`/`depends_on`, tests, and the summary). For a file it emits the ordered
event log (`def`/`theorem`/`proof`/`test`/… each with a `status`). Exit code is
non-zero iff something failed, so it drops straight into automation.
