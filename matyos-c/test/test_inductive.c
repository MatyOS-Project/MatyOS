/* M3 tests: inductive types, auto-generated recursors, iota-reduction and the
 * strict-positivity guard (mirrors kernel/inductive.py + demo_*). */
#include "../src/infer.h"
#include "../src/env.h"
#include <stdio.h>

static int failures = 0;
static Arena *AR;

#define C(n)      mk_const(AR, (n))
#define APP(f,x)  mk_app(AR, (f), (x))

static void show_type(const char *nm) {
    Term *ty = env_const_type(nm);
    printf("    %-8s : ", nm);
    if (ty) tm_print(ty); else printf("<undeclared>");
    printf("\n");
}

static void expect_eq(const char *what, Term *got, Term *want) {
    if (tm_def_equal(AR, got, want)) {
        printf("  [OK] %s = ", what); tm_print(tm_normalize(AR, got)); printf("\n");
    } else {
        printf("  [FAIL] %s: got ", what); tm_print(tm_normalize(AR, got));
        printf(", want "); tm_print(tm_normalize(AR, want)); printf("\n");
        failures++;
    }
}

int main(void) {
    AR = arena_new();
    env_reset();

    /* ---- Bool ---- */
    SCtor bctors[] = {
        { "true",  0, NULL },
        { "false", 0, NULL },
    };
    const char *bool_rec = declare_inductive(AR, "Bool", 0, NULL, 0, 2, bctors, 0);
    if (!bool_rec) { printf("  [FAIL] declare Bool: %s\n", env_err); failures++; }
    else printf("  [OK] declared Bool (recursor %s)\n", bool_rec);

    /* ---- Nat ---- */
    SArg succ_args[] = { { "n", s_rec() } };     /* succ : Nat -> Nat (recursive) */
    SCtor nctors[] = {
        { "zero", 0, NULL },
        { "succ", 1, succ_args },
    };
    const char *nat_rec = declare_inductive(AR, "Nat", 0, NULL, 0, 2, nctors, 0);
    if (!nat_rec) { printf("  [FAIL] declare Nat: %s\n", env_err); failures++; }
    else printf("  [OK] declared Nat (recursor %s)\n", nat_rec);

    printf("  generated types:\n");
    show_type("Bool"); show_type("true"); show_type("Bool.rec");
    show_type("Nat"); show_type("zero"); show_type("succ"); show_type("Nat.rec");

    /* numerals */
    Term *zero = C("zero");
    Term *one  = APP(C("succ"), zero);
    Term *two  = APP(C("succ"), one);
    Term *three= APP(C("succ"), two);

    /* type-check that `two : Nat` in the trusted checker */
    Term *two_ty = infer(AR, NULL, two);
    if (two_ty && tm_def_equal(AR, two_ty, C("Nat")))
        printf("  [OK] succ (succ zero) : Nat\n");
    else { printf("  [FAIL] two : Nat (%s)\n", two_ty ? "wrong type" : infer_err); failures++; }

    /* ---- compute with Bool.rec ----
       Bool.rec (fun _:Bool => Nat) zero one true  ==>  zero
       Bool.rec (fun _:Bool => Nat) zero one false ==>  one          */
    Term *Pbool = mk_lam(AR, C("Bool"), C("Nat"));   /* fun _:Bool => Nat */
    Term *if_true  = APP(APP(APP(APP(C("Bool.rec"), Pbool), zero), one), C("true"));
    Term *if_false = APP(APP(APP(APP(C("Bool.rec"), Pbool), zero), one), C("false"));
    expect_eq("Bool.rec .. true",  if_true,  zero);
    expect_eq("Bool.rec .. false", if_false, one);

    /* ---- compute with Nat.rec: addition by structural recursion ----
       add m n = Nat.rec (fun _:Nat => Nat) n (fun k ih => succ ih) m       */
    Term *Pnat   = mk_lam(AR, C("Nat"), C("Nat"));                 /* fun _:Nat => Nat */
    Term *e_succ = mk_lam(AR, C("Nat"),                            /* fun (k:Nat) => */
                     mk_lam(AR, C("Nat"),                          /* fun (ih:Nat) => */
                       APP(C("succ"), mk_var(AR, 0))));            /* succ ih */
    /* add(m,n) = Nat.rec Pnat n e_succ m */
    #define ADD(m,n) APP(APP(APP(APP(C("Nat.rec"), Pnat), (n)), e_succ), (m))
    expect_eq("2 + 1", ADD(two, one), three);
    expect_eq("0 + 2", ADD(zero, two), two);
    expect_eq("1 + 1", ADD(one, one), two);

    /* the add term itself type-checks to Nat */
    Term *add21_ty = infer(AR, NULL, ADD(two, one));
    if (add21_ty && tm_def_equal(AR, add21_ty, C("Nat")))
        printf("  [OK] (2 + 1) : Nat\n");
    else { printf("  [FAIL] (2+1) : Nat (%s)\n", add21_ty ? "wrong type" : infer_err); failures++; }

    /* ---- strict positivity: reject  Bad  with  mk : (Bad -> Bad) -> Bad ---- */
    SArg bad_args[] = { { "f", s_pi(AR, "_", s_const(AR, "Bad"), s_const(AR, "Bad")) } };
    SCtor bad_ctors[] = { { "mk", 1, bad_args } };
    const char *bad = declare_inductive(AR, "Bad", 0, NULL, 0, 1, bad_ctors, 0);
    if (!bad) printf("  [OK] non-positive inductive rejected (%s)\n", env_err);
    else { printf("  [FAIL] non-positive inductive was accepted!\n"); failures++; }

    printf("\nM3: %s (%d failure%s)\n", failures ? "FAIL" : "OK",
           failures, failures == 1 ? "" : "s");
    arena_free(AR);
    return failures ? 1 : 0;
}
