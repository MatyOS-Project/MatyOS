#include "infer.h"
#include <stdio.h>
#include <string.h>

char infer_err[256];

Ctx *ctx_cons(Arena *ar, Term *ty, Ctx *rest) {
    Ctx *c = (Ctx *)arena_alloc(ar, sizeof(Ctx));
    c->ty = ty; c->rest = rest;
    return c;
}

static int is_sort(Term *t) { return t->kind == T_UNIV || t->kind == T_PROP; }
static int sort_level(Term *t) { return t->kind == T_PROP ? 0 : t->i; }

#define FAIL(...) do { snprintf(infer_err, sizeof infer_err, __VA_ARGS__); return NULL; } while (0)

Term *infer(Arena *ar, Ctx *ctx, Term *t) {
    switch (t->kind) {
    case T_UNIV:
        return mk_univ(ar, t->i + 1);            /* Type i : Type (i+1) */
    case T_PROP:
        return mk_univ(ar, 0);                   /* Prop : Type0 */
    case T_CONST:
        FAIL("unknown constant: %s", t->name);   /* no environment until M3 */
    case T_VAR: {
        Ctx *c = ctx; int k = t->i;
        while (k > 0 && c) { c = c->rest; k--; }
        if (k != 0 || !c) FAIL("unbound variable #%d", t->i);
        return tm_shift(ar, c->ty, t->i + 1, 0);
    }
    case T_PI: {
        Term *sd = infer(ar, ctx, t->a);
        if (!sd) return NULL;
        sd = tm_normalize(ar, sd);
        if (!is_sort(sd)) FAIL("Pi domain is not a type");
        Term *sc = infer(ar, ctx_cons(ar, t->a, ctx), t->b);
        if (!sc) return NULL;
        sc = tm_normalize(ar, sc);
        if (!is_sort(sc)) FAIL("Pi codomain is not a type");
        /* imax rule: a product into Prop is impredicative (stays Prop). */
        if (sc->kind == T_PROP) return mk_prop(ar);
        int lvl = sort_level(sd) > sc->i ? sort_level(sd) : sc->i;
        return mk_univ(ar, lvl);
    }
    case T_LAM: {
        Term *sd = infer(ar, ctx, t->a);
        if (!sd) return NULL;
        if (!is_sort(tm_normalize(ar, sd))) FAIL("lambda domain is not a type");
        Term *bt = infer(ar, ctx_cons(ar, t->a, ctx), t->b);
        if (!bt) return NULL;
        return mk_pi(ar, t->a, bt);
    }
    case T_APP: {
        Term *ft = infer(ar, ctx, t->a);
        if (!ft) return NULL;
        ft = tm_normalize(ar, ft);
        if (ft->kind != T_PI) FAIL("applying a non-function");
        Term *xt = infer(ar, ctx, t->b);
        if (!xt) return NULL;
        if (!tm_def_equal(ar, xt, ft->a)) FAIL("argument type mismatch");
        return tm_beta(ar, ft->b, t->b);         /* substitute the argument */
    }
    }
    FAIL("infer: unknown term");
}

int type_check(Arena *ar, Term *term, Term *expected) {
    Term *got = infer(ar, NULL, term);
    return got && tm_def_equal(ar, got, expected);
}
