/* M7 tests: the tactic engine — intro/exact/assumption/refl/rewrite/
 * induction/apply/auto, driven through `proof ... := by ... qed`. */
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
    "inductive Nat : Type :=\n"
    "  | zero : Nat\n"
    "  | succ : Nat -> Nat\n"
    "def add (m : Nat) (n : Nat) : Nat :=\n"
    "  Nat.rec (fun (_ : Nat) => Nat) n (fun (k : Nat) (ih : Nat) => succ ih) m\n"
    "\n"
    "-- intro + exact\n"
    "theorem idt : forall (A : Type), A -> A\n"
    "proof idt := by intro A intro x exact x qed\n"
    "\n"
    "-- induction + rewrite + refl:  n + 0 = n\n"
    "theorem add0 : forall (n : Nat), Eq Nat (add n zero) n\n"
    "proof add0 := by induction n refl intro k ih rewrite ih refl qed\n"
    "\n"
    "-- auto finds modus ponens\n"
    "theorem mp : forall (A : Type) (B : Type), (A -> B) -> A -> B\n"
    "proof mp := by auto qed\n"
    "\n"
    "-- apply + assumption\n"
    "theorem ap : forall (A : Type) (B : Type), (A -> B) -> A -> B\n"
    "proof ap := by intro A intro B intro f intro a apply f assumption qed\n";

static const char *BAD =
    "inductive Nat : Type := | zero : Nat | succ : Nat -> Nat\n"
    "theorem bad : Eq Nat zero (succ zero)\n"
    "proof bad := by refl qed\n";     /* refl on 0 = 1 must fail */

int main(void) {
    expect("intro/exact/induction/rewrite/refl/auto/apply all prove", GOOD, 0);
    expect("refl on a false equality fails", BAD, 1);

    printf("\nM7: %s (%d failure%s)\n", failures ? "FAIL" : "OK",
           failures, failures == 1 ? "" : "s");
    return failures ? 1 : 0;
}
