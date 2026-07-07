/* M5 tests: the .elk front end — tokenizer + parser + executor, end to end. */
#include "../src/check.h"
#include <stdio.h>

static int failures = 0;

static void expect(const char *label, const char *src, int want) {
    Arena *ar = arena_new();
    int f = elk_run_source(ar, src, 0);
    if (f == want) printf("  [OK] %s (failures=%d)\n", label, f);
    else { printf("  [FAIL] %s: got %d, want %d (parse_err='%s')\n", label, f, want, parse_err); failures++; }
    arena_free(ar);
}

static const char *GOOD =
    "-- Peano naturals with addition, checked end to end\n"
    "inductive Nat : Type :=\n"
    "  | zero : Nat\n"
    "  | succ : Nat -> Nat\n"
    "\n"
    "def add (m : Nat) (n : Nat) : Nat :=\n"
    "  Nat.rec (fun (_ : Nat) => Nat) n (fun (k : Nat) (ih : Nat) => succ ih) m\n"
    "\n"
    "check add\n"
    "eval add (succ (succ zero)) (succ zero)\n"
    "-- 1 + 0 computes to 1, provable by refl\n"
    "example : Eq Nat (add (succ zero) zero) (succ zero) := refl Nat (succ zero)\n"
    "def one : Nat := succ zero\n"
    "example : forall (A : Type), forall (a : A), Eq A a a :=\n"
    "  fun (A : Type) (a : A) => refl A a\n";

static const char *BAD_PROOF =
    "inductive Nat : Type := | zero : Nat | succ : Nat -> Nat\n"
    "example : Eq Nat zero (succ zero) := refl Nat zero\n";   /* 0 != 1 */

static const char *AXIOM_OK =
    "axiom P : Prop\n"
    "axiom h : P\n"
    "check h\n";

int main(void) {
    expect("arithmetic program (def/inductive/check/eval/example)", GOOD, 0);
    expect("wrong proof is rejected", BAD_PROOF, 1);
    expect("axiom + check", AXIOM_OK, 0);

    printf("\nM5: %s (%d failure%s)\n", failures ? "FAIL" : "OK",
           failures, failures == 1 ? "" : "s");
    return failures ? 1 : 0;
}
