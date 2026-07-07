#include "term.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

TmDeltaHook tm_delta_hook = NULL;   /* set by env.c when an environment loads */
TmIotaHook  tm_iota_hook  = NULL;

/* ---- arena ---- */
#define ARENA_BLOCK (1 << 16)
struct Arena {
    char  *buf;
    size_t used, cap;
    struct Arena *next;   /* previous blocks (freed together) */
};

Arena *arena_new(void) {
    Arena *ar = (Arena *)malloc(sizeof(Arena));
    ar->buf = (char *)malloc(ARENA_BLOCK);
    ar->used = 0; ar->cap = ARENA_BLOCK; ar->next = NULL;
    return ar;
}
void arena_free(Arena *ar) {
    while (ar) { Arena *n = ar->next; free(ar->buf); free(ar); ar = n; }
}
void *arena_alloc(Arena *ar, size_t n) {
    n = (n + 15) & ~((size_t)15);              /* 16-byte align */
    if (ar->used + n > ar->cap) {              /* grow: push a fresh head block */
        size_t cap = n > ARENA_BLOCK ? n : ARENA_BLOCK;
        Arena *old = (Arena *)malloc(sizeof(Arena));
        *old = *ar;                            /* copy current block into a node */
        ar->buf = (char *)malloc(cap);
        ar->used = 0; ar->cap = cap; ar->next = old;
    }
    void *p = ar->buf + ar->used;
    ar->used += n;
    return p;
}
char *arena_strdup(Arena *ar, const char *s) {
    size_t n = strlen(s) + 1;
    char *p = (char *)arena_alloc(ar, n);
    memcpy(p, s, n);
    return p;
}

/* ---- constructors ---- */
static Term *mk(Arena *ar, TermKind k) {
    Term *t = (Term *)arena_alloc(ar, sizeof(Term));
    t->kind = k; t->i = 0; t->name = NULL; t->a = t->b = NULL;
    return t;
}
Term *mk_var(Arena *ar, int index) { Term *t = mk(ar, T_VAR); t->i = index; return t; }
Term *mk_univ(Arena *ar, int level){ Term *t = mk(ar, T_UNIV); t->i = level; return t; }
Term *mk_prop(Arena *ar)           { return mk(ar, T_PROP); }
Term *mk_const(Arena *ar, const char *name) {
    Term *t = mk(ar, T_CONST); t->name = arena_strdup(ar, name); return t;
}
Term *mk_pi(Arena *ar, Term *dom, Term *cod) {
    Term *t = mk(ar, T_PI); t->a = dom; t->b = cod; return t;
}
Term *mk_lam(Arena *ar, Term *dom, Term *body) {
    Term *t = mk(ar, T_LAM); t->a = dom; t->b = body; return t;
}
Term *mk_app(Arena *ar, Term *fn, Term *arg) {
    Term *t = mk(ar, T_APP); t->a = fn; t->b = arg; return t;
}
Term *mk_meta(Arena *ar, int id) { Term *t = mk(ar, T_META); t->i = id; return t; }

/* ---- shift / subst ---- */
Term *tm_shift(Arena *ar, Term *t, int d, int c) {
    switch (t->kind) {
    case T_VAR:  return t->i >= c ? mk_var(ar, t->i + d) : t;
    case T_UNIV: case T_PROP: case T_CONST: case T_META: return t;
    case T_PI:   return mk_pi (ar, tm_shift(ar, t->a, d, c), tm_shift(ar, t->b, d, c + 1));
    case T_LAM:  return mk_lam(ar, tm_shift(ar, t->a, d, c), tm_shift(ar, t->b, d, c + 1));
    case T_APP:  return mk_app(ar, tm_shift(ar, t->a, d, c), tm_shift(ar, t->b, d, c));
    }
    return t;
}
Term *tm_subst(Arena *ar, Term *t, int j, Term *s) {
    switch (t->kind) {
    case T_VAR:  return t->i == j ? s : t;
    case T_UNIV: case T_PROP: case T_CONST: case T_META: return t;
    case T_PI:   return mk_pi (ar, tm_subst(ar, t->a, j, s),
                               tm_subst(ar, t->b, j + 1, tm_shift(ar, s, 1, 0)));
    case T_LAM:  return mk_lam(ar, tm_subst(ar, t->a, j, s),
                               tm_subst(ar, t->b, j + 1, tm_shift(ar, s, 1, 0)));
    case T_APP:  return mk_app(ar, tm_subst(ar, t->a, j, s), tm_subst(ar, t->b, j, s));
    }
    return t;
}
Term *tm_beta(Arena *ar, Term *body, Term *arg) {
    return tm_shift(ar, tm_subst(ar, body, 0, tm_shift(ar, arg, 1, 0)), -1, 0);
}

/* ---- normalize (full beta normal form) ---- */
Term *tm_normalize(Arena *ar, Term *t) {
    switch (t->kind) {
    case T_VAR: case T_UNIV: case T_PROP: case T_META: return t;
    case T_CONST: {
        if (tm_delta_hook) {                       /* delta: unfold a definition */
            Term *v = tm_delta_hook(ar, t);
            if (v) return tm_normalize(ar, v);
        }
        return t;
    }
    case T_PI:  return mk_pi (ar, tm_normalize(ar, t->a), tm_normalize(ar, t->b));
    case T_LAM: return mk_lam(ar, tm_normalize(ar, t->a), tm_normalize(ar, t->b));
    case T_APP: {
        Term *f = tm_normalize(ar, t->a);
        Term *x = tm_normalize(ar, t->b);
        if (f->kind == T_LAM) return tm_normalize(ar, tm_beta(ar, f->b, x));
        if (tm_iota_hook) {                        /* iota: fire a recursor */
            Term *r = tm_iota_hook(ar, mk_app(ar, f, x));
            if (r) return tm_normalize(ar, r);
        }
        return mk_app(ar, f, x);
    }
    }
    return t;
}

/* ---- equality ---- */
int tm_eq(Term *x, Term *y) {
    if (x == y) return 1;
    if (x->kind != y->kind) return 0;
    switch (x->kind) {
    case T_VAR:  return x->i == y->i;
    case T_UNIV: return x->i == y->i;
    case T_META: return x->i == y->i;
    case T_PROP: return 1;
    case T_CONST:return strcmp(x->name, y->name) == 0;
    case T_PI: case T_LAM: case T_APP:
        return tm_eq(x->a, y->a) && tm_eq(x->b, y->b);
    }
    return 0;
}
int tm_def_equal(Arena *ar, Term *x, Term *y) {
    return tm_eq(tm_normalize(ar, x), tm_normalize(ar, y));
}

/* ---- printer ---- */
void tm_print(Term *t) {
    switch (t->kind) {
    case T_VAR:  printf("#%d", t->i); break;
    case T_UNIV: printf("Type%d", t->i); break;
    case T_PROP: printf("Prop"); break;
    case T_CONST:printf("%s", t->name); break;
    case T_PI:   printf("(Pi "); tm_print(t->a); printf(" -> "); tm_print(t->b); printf(")"); break;
    case T_LAM:  printf("(fun "); tm_print(t->a); printf(" => "); tm_print(t->b); printf(")"); break;
    case T_APP:  printf("("); tm_print(t->a); printf(" "); tm_print(t->b); printf(")"); break;
    case T_META: printf("?%d", t->i); break;
    }
}
