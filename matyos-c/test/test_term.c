/* M1 tests: arena + de Bruijn terms + shift/subst/normalize/def_equal. */
#include "../src/term.h"
#include <stdio.h>

static int failures = 0;
#define CHECK(cond, msg) do { \
    if (cond) { printf("  [OK] %s\n", msg); } \
    else { printf("  [FAIL] %s\n", msg); failures++; } } while (0)

int main(void) {
    Arena *ar = arena_new();

    /* beta: (fun (_:Type0) => #0) applied to a constant c  ==>  c */
    Term *idf = mk_lam(ar, mk_univ(ar, 0), mk_var(ar, 0));
    Term *c   = mk_const(ar, "c");
    Term *app = mk_app(ar, idf, c);
    CHECK(tm_def_equal(ar, app, c), "beta: (fun x => x) c == c");

    /* K applied to two args: (fun _ => fun _ => #1) a b  ==>  a */
    Term *k = mk_lam(ar, mk_univ(ar, 0),
                mk_lam(ar, mk_univ(ar, 0), mk_var(ar, 1)));
    Term *a = mk_const(ar, "a"), *b = mk_const(ar, "b");
    Term *kab = mk_app(ar, mk_app(ar, k, a), b);
    CHECK(tm_def_equal(ar, kab, a), "K a b == a");

    /* shift lifts free variables, leaves bound ones */
    Term *v0 = mk_var(ar, 0), *v1 = mk_var(ar, 1);
    CHECK(tm_eq(tm_shift(ar, v0, 2, 0), mk_var(ar, 2)), "shift #0 by 2 == #2");
    CHECK(tm_eq(tm_shift(ar, mk_lam(ar, mk_prop(ar), v0), 5, 0),
                mk_lam(ar, mk_prop(ar), v0)),
          "shift under a binder keeps the bound var");
    CHECK(tm_eq(tm_shift(ar, mk_lam(ar, mk_prop(ar), v1), 5, 0),
                mk_lam(ar, mk_prop(ar), mk_var(ar, 6))),
          "shift under a binder lifts the free var");

    /* structural inequality of distinct constants */
    CHECK(!tm_def_equal(ar, a, b), "a != b");

    /* Prop and Type are distinct */
    CHECK(!tm_def_equal(ar, mk_prop(ar), mk_univ(ar, 0)), "Prop != Type0");

    printf("\nM1: %s (%d failure%s)\n", failures ? "FAIL" : "OK",
           failures, failures == 1 ? "" : "s");
    arena_free(ar);
    return failures ? 1 : 0;
}
