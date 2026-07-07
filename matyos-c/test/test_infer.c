/* M2 tests: the type checker proves the standard combinators and rejects
 * ill-typed terms (Curry-Howard proofs, mirroring kernel/demo.py). */
#include "../src/infer.h"
#include <stdio.h>

static int failures = 0;

static void ok_typed(const char *name, Arena *ar, Term *term) {
    Term *ty = infer(ar, NULL, term);
    if (ty) { printf("  [OK] %s : ", name); tm_print(ty); printf("\n"); }
    else { printf("  [FAIL] %s : %s\n", name, infer_err); failures++; }
}
static void must_reject(const char *name, Arena *ar, Term *term) {
    Term *ty = infer(ar, NULL, term);
    if (!ty) printf("  [OK] %s rejected (%s)\n", name, infer_err);
    else { printf("  [FAIL] %s was accepted!\n", name); failures++; }
}

int main(void) {
    Arena *ar = arena_new();
    Term *Ty = mk_univ(ar, 0);
    Term *v0 = mk_var(ar, 0), *v1 = mk_var(ar, 1), *v2 = mk_var(ar, 2);
    Term *v3 = mk_var(ar, 3), *v4 = mk_var(ar, 4);

    /* identity: fun (A:Type0) (x:A) => x */
    Term *id = mk_lam(ar, Ty, mk_lam(ar, v0, v0));
    ok_typed("identity", ar, id);

    /* K: fun (A B:Type0) (a:A) (b:B) => a */
    Term *k_body = mk_lam(ar, v1, mk_lam(ar, v1, v1));
    Term *k = mk_lam(ar, Ty, mk_lam(ar, Ty, k_body));
    ok_typed("K (A->B->A)", ar, k);

    /* modus ponens: fun (A B:Type0) (f:A->B) (a:A) => f a
       under A(#1),B(#0):  A->B = Pi(#1, #1)   (B shifted under the arrow) */
    Term *fAB = mk_pi(ar, v1, v1);
    Term *mp_inner = mk_lam(ar, fAB, mk_lam(ar, v2, mk_app(ar, v1, v0)));
    Term *mp = mk_lam(ar, Ty, mk_lam(ar, Ty, mp_inner));
    ok_typed("modus_ponens", ar, mp);

    /* composition: fun (A B C:Type0) (g:B->C) (f:A->B) (x:A) => g (f x) */
    Term *gBC  = mk_pi(ar, v1, v1);          /* under A#2,B#1,C#0 */
    Term *fAB2 = mk_pi(ar, v3, v3);          /* under g#0,C#1,B#2,A#3 */
    Term *comp_body = mk_app(ar, v2, mk_app(ar, v1, v0));
    Term *comp = mk_lam(ar, Ty, mk_lam(ar, Ty, mk_lam(ar, Ty,
                   mk_lam(ar, gBC, mk_lam(ar, fAB2, mk_lam(ar, v4, comp_body))))));
    ok_typed("composition", ar, comp);

    /* bogus: fun (A:Type0) (x:A) => x x   -- x is not a function */
    Term *bogus = mk_lam(ar, Ty, mk_lam(ar, v0, mk_app(ar, v0, v0)));
    must_reject("self-application (x x)", ar, bogus);

    /* impredicative Prop: (forall P:Prop, P) : Prop */
    Term *fpt = infer(ar, NULL, mk_pi(ar, mk_prop(ar), v0));
    if (fpt && fpt->kind == T_PROP)
        printf("  [OK] (forall P:Prop, P) : Prop  (impredicative)\n");
    else { printf("  [FAIL] impredicative Prop\n"); failures++; }

    /* predicative contrast: (forall A:Type0, A) : Type1 */
    Term *bpt = infer(ar, NULL, mk_pi(ar, Ty, v0));
    if (bpt && bpt->kind == T_UNIV && bpt->i == 1)
        printf("  [OK] (forall A:Type0, A) : Type1  (predicative)\n");
    else { printf("  [FAIL] predicative Type\n"); failures++; }

    printf("\nM2: %s (%d failure%s)\n", failures ? "FAIL" : "OK",
           failures, failures == 1 ? "" : "s");
    arena_free(ar);
    return failures ? 1 : 0;
}
