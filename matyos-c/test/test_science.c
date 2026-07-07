/* M6 tests: the scientific-method commands (theorem/proof/hypothesis/
 * conjecture/test) and certified-vs-conditional (realistic) tracking. */
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

static const char *CERTIFIED =
    "inductive Nat : Type := | zero : Nat | succ : Nat -> Nat\n"
    "theorem triv : forall (A : Type), A -> A\n"
    "proof triv := fun (A : Type) (x : A) => x\n"
    "test t1 : succ zero = succ zero\n";

static const char *CONDITIONAL =
    "conjecture cheat : forall (A : Type), A\n"
    "theorem anything : forall (A : Type), A\n"
    "proof anything := cheat\n";                 /* PROVEN but conditional on cheat (not a failure) */

static const char *BAD_PROOF =
    "theorem bogus : forall (A : Type), A\n"
    "proof bogus := fun (A : Type) => A\n";       /* term : forall A, Type, not forall A, A */

static const char *NO_THEOREM =
    "proof ghost := Prop\n";                       /* no such theorem */

static const char *FAIL_TEST =
    "inductive Nat : Type := | zero : Nat | succ : Nat -> Nat\n"
    "test bad : zero = succ zero\n";               /* 0 != 1 */

int main(void) {
    expect("certified theorem + passing test", CERTIFIED, 0);
    expect("proof conditional on a conjecture (still PROVEN)", CONDITIONAL, 0);
    expect("ill-typed proof rejected", BAD_PROOF, 1);
    expect("proof without a theorem rejected", NO_THEOREM, 1);
    expect("failing test detected", FAIL_TEST, 1);

    printf("\nM6: %s (%d failure%s)\n", failures ? "FAIL" : "OK",
           failures, failures == 1 ? "" : "s");
    return failures ? 1 : 0;
}
