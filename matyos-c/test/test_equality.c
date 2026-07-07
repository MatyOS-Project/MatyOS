/* M4 tests: propositional equality Eq/refl, the based J eliminator and its
 * computation rule; the J-derived lemmas symm/trans/cong/subst; and that
 * transport/cong along refl actually reduces (mirrors stdlib/eq.elk). */
#include "../src/infer.h"
#include "../src/env.h"
#include <stdio.h>

static int failures = 0;
static Arena *AR;

/* surface-term shorthands */
#define SV(n)   s_var(AR, (n))
#define SC(n)   s_const(AR, (n))
#define UU      s_univ(AR, 0)
#define PI(n,d,c)  s_pi(AR, (n), (d), (c))
#define LM(n,d,b)  s_lam(AR, (n), (d), (b))
#define ARROW(d,c) s_pi(AR, "_", (d), (c))
#define AP(f,x)    s_app(AR, (f), (x))
#define AP2(f,a,b) AP(AP((f),(a)),(b))
#define AP3(f,a,b,c) AP(AP2((f),(a),(b)),(c))
#define EQ(A,x,y)  AP3(SC("Eq"), (A), (x), (y))
#define REFL(A,x)  AP2(SC("refl"), (A), (x))
#define J6(A,a,P,d,b,e) AP(AP(AP(AP(AP(AP(SC("Eq.J"),(A)),(a)),(P)),(d)),(b)),(e))

static void def(const char *name, SNode *ty, SNode *val) {
    Term *t = s_to_term(AR, ty), *v = s_to_term(AR, val);
    if (t && v && env_define(AR, name, t, v)) {
        printf("  [OK] def %-6s : ", name); tm_print(t); printf("\n");
    } else { printf("  [FAIL] def %s: %s\n", name, env_err); failures++; }
}

static void expect_eq(const char *what, SNode *got_s, SNode *want_s) {
    Term *got = s_to_term(AR, got_s), *want = s_to_term(AR, want_s);
    if (got && want && tm_def_equal(AR, got, want)) {
        printf("  [OK] %s ==> ", what); tm_print(tm_normalize(AR, got)); printf("\n");
    } else {
        printf("  [FAIL] %s: got ", what);
        if (got) tm_print(tm_normalize(AR, got)); else printf("<err>");
        printf(", want "); if (want) tm_print(tm_normalize(AR, want)); printf("\n");
        failures++;
    }
}

static void expect_typechecks(const char *what, SNode *term_s, SNode *type_s) {
    Term *tm = s_to_term(AR, term_s), *ty = s_to_term(AR, type_s);
    Term *got = tm ? infer(AR, NULL, tm) : NULL;
    if (got && ty && tm_def_equal(AR, got, ty))
        printf("  [OK] %s : (as expected)\n", what);
    else { printf("  [FAIL] %s: %s\n", what, got ? "type mismatch" : infer_err); failures++; }
}

int main(void) {
    AR = arena_new();
    env_reset();
    env_setup_equality(AR);

    /* Nat, for concrete computation */
    SArg succ_args[] = { { "n", s_rec() } };
    SCtor nctors[] = { { "zero", 0, NULL }, { "succ", 1, succ_args } };
    if (!declare_inductive(AR, "Nat", 0, NULL, 0, 2, nctors, 0)) {
        printf("  [FAIL] declare Nat: %s\n", env_err); failures++;
    }

    printf("  primitives:\n");
    printf("    Eq    : "); tm_print(env_const_type("Eq"));   printf("\n");
    printf("    refl  : "); tm_print(env_const_type("refl")); printf("\n");
    printf("    Eq.J  : "); tm_print(env_const_type("Eq.J")); printf("\n");

    /* ---- the J-derived toolkit (mirrors stdlib/eq.elk) ---- */
    /* symm : (A)(a)(b)(e:Eq A a b) -> Eq A b a */
    def("symm",
        PI("A", UU, PI("a", SV("A"), PI("b", SV("A"),
          PI("e", EQ(SV("A"), SV("a"), SV("b")), EQ(SV("A"), SV("b"), SV("a")))))),
        LM("A", UU, LM("a", SV("A"), LM("b", SV("A"),
          LM("e", EQ(SV("A"), SV("a"), SV("b")),
            J6(SV("A"), SV("a"),
               LM("x", SV("A"), LM("_", EQ(SV("A"), SV("a"), SV("x")),
                                    EQ(SV("A"), SV("x"), SV("a")))),
               REFL(SV("A"), SV("a")), SV("b"), SV("e")))))));

    /* trans : (A)(a)(b)(c)(e1:Eq A a b)(e2:Eq A b c) -> Eq A a c */
    def("trans",
        PI("A", UU, PI("a", SV("A"), PI("b", SV("A"), PI("c", SV("A"),
          PI("e1", EQ(SV("A"), SV("a"), SV("b")),
            PI("e2", EQ(SV("A"), SV("b"), SV("c")), EQ(SV("A"), SV("a"), SV("c")))))))),
        LM("A", UU, LM("a", SV("A"), LM("b", SV("A"), LM("c", SV("A"),
          LM("e1", EQ(SV("A"), SV("a"), SV("b")),
            LM("e2", EQ(SV("A"), SV("b"), SV("c")),
              J6(SV("A"), SV("b"),
                 LM("x", SV("A"), LM("_", EQ(SV("A"), SV("b"), SV("x")),
                                      EQ(SV("A"), SV("a"), SV("x")))),
                 SV("e1"), SV("c"), SV("e2")))))))));

    /* cong : (A)(B)(f:A->B)(a)(b)(e:Eq A a b) -> Eq B (f a) (f b) */
    def("cong",
        PI("A", UU, PI("B", UU, PI("f", ARROW(SV("A"), SV("B")),
          PI("a", SV("A"), PI("b", SV("A"),
            PI("e", EQ(SV("A"), SV("a"), SV("b")),
              EQ(SV("B"), AP(SV("f"), SV("a")), AP(SV("f"), SV("b"))))))))),
        LM("A", UU, LM("B", UU, LM("f", ARROW(SV("A"), SV("B")),
          LM("a", SV("A"), LM("b", SV("A"),
            LM("e", EQ(SV("A"), SV("a"), SV("b")),
              J6(SV("A"), SV("a"),
                 LM("x", SV("A"), LM("_", EQ(SV("A"), SV("a"), SV("x")),
                                      EQ(SV("B"), AP(SV("f"), SV("a")), AP(SV("f"), SV("x"))))),
                 REFL(SV("B"), AP(SV("f"), SV("a"))), SV("b"), SV("e")))))))));

    /* subst : (A)(a)(b)(P:A->Type)(e:Eq A a b)(pa:P a) -> P b */
    def("subst",
        PI("A", UU, PI("a", SV("A"), PI("b", SV("A"), PI("P", ARROW(SV("A"), UU),
          PI("e", EQ(SV("A"), SV("a"), SV("b")),
            PI("pa", AP(SV("P"), SV("a")), AP(SV("P"), SV("b")))))))),
        LM("A", UU, LM("a", SV("A"), LM("b", SV("A"), LM("P", ARROW(SV("A"), UU),
          LM("e", EQ(SV("A"), SV("a"), SV("b")),
            LM("pa", AP(SV("P"), SV("a")),
              J6(SV("A"), SV("a"),
                 LM("x", SV("A"), LM("_", EQ(SV("A"), SV("a"), SV("x")), AP(SV("P"), SV("x")))),
                 SV("pa"), SV("b"), SV("e")))))))));

    /* ---- the J computation rule fires (transport/cong/symm/trans along refl) ---- */
    printf("  computation (J on refl reduces):\n");
    SNode *Nat = SC("Nat"), *zero = SC("zero");
    SNode *one = AP(SC("succ"), zero);
    SNode *Pconst = LM("_", Nat, Nat);      /* fun _:Nat => Nat */

    /* symm Nat 0 0 (refl 0)  ==>  refl 0 */
    expect_eq("symm 0 0 (refl 0)",
        AP2(AP2(SC("symm"), Nat, zero), zero, REFL(Nat, zero)),
        REFL(Nat, zero));
    /* trans Nat 0 0 0 (refl 0) (refl 0)  ==>  refl 0 */
    expect_eq("trans (refl 0) (refl 0)",
        AP2(AP2(AP2(SC("trans"), Nat, zero), zero, zero), REFL(Nat, zero), REFL(Nat, zero)),
        REFL(Nat, zero));
    /* cong Nat Nat succ 0 0 (refl 0)  ==>  refl (succ 0) */
    expect_eq("cong succ (refl 0)",
        AP2(AP2(AP2(SC("cong"), Nat, Nat), SC("succ"), zero), zero, REFL(Nat, zero)),
        REFL(Nat, one));
    /* subst Nat 0 0 (fun _=>Nat) (refl 0) 1  ==>  1 */
    expect_eq("subst .. (refl 0) 1",
        AP2(AP2(AP2(SC("subst"), Nat, zero), zero, Pconst), REFL(Nat, zero), one),
        one);

    /* ---- reflexivity example (eq.elk): fun A a => symm A a a (refl A a) ---- */
    expect_typechecks("fun A a => symm A a a (refl A a)",
        LM("A", UU, LM("a", SV("A"),
          AP2(AP2(SC("symm"), SV("A"), SV("a")), SV("a"), REFL(SV("A"), SV("a"))))),
        PI("A", UU, PI("a", SV("A"), EQ(SV("A"), SV("a"), SV("a")))));

    printf("\nM4: %s (%d failure%s)\n", failures ? "FAIL" : "OK",
           failures, failures == 1 ? "" : "s");
    arena_free(AR);
    return failures ? 1 : 0;
}
