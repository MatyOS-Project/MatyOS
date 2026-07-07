#include "tactics.h"
#include "infer.h"
#include "env.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

char tactic_err[256];
#define FAILT(...) do { snprintf(tactic_err, sizeof tactic_err, __VA_ARGS__); return 0; } while (0)

/* ===================== proof state ===================== */
typedef struct {
    Term **ctx; const char **names; int n;   /* hypotheses (ctx[0] = Var 0) */
    Term *target; Term *solution;             /* solution NULL until closed  */
} Goal;

typedef struct {
    Arena *ar;
    Goal **metas; int nmetas, mcap;   /* goal id -> Goal* (stable pointers)  */
    int   *queue;  int qn, qcap;       /* open goal ids; front = queue[0]     */
} Session;

static void sess_init(Session *S, Arena *ar) {
    S->ar = ar;
    S->mcap = 16; S->nmetas = 0; S->metas = (Goal **)malloc(sizeof(Goal *) * S->mcap);
    S->qcap = 16; S->qn = 0;     S->queue = (int *)malloc(sizeof(int) * S->qcap);
}
static void sess_free(Session *S) { free(S->metas); free(S->queue); }

static int new_goal(Session *S, Term **ctx, const char **names, int n, Term *target) {
    if (S->nmetas == S->mcap) { S->mcap *= 2; S->metas = realloc(S->metas, sizeof(Goal *) * S->mcap); }
    Goal *g = (Goal *)arena_alloc(S->ar, sizeof(Goal));
    g->ctx = ctx; g->names = names; g->n = n; g->target = target; g->solution = NULL;
    S->metas[S->nmetas] = g;
    return S->nmetas++;
}
static void q_ensure(Session *S, int need) {
    if (need <= S->qcap) return;
    while (S->qcap < need) S->qcap *= 2;
    S->queue = (int *)realloc(S->queue, sizeof(int) * S->qcap);
}
static void pop_front(Session *S) { for (int i = 1; i < S->qn; i++) S->queue[i-1] = S->queue[i]; S->qn--; }
static void replace_front(Session *S, int *kids, int nk) {
    int rest = S->qn - 1;
    q_ensure(S, nk + rest);
    memmove(&S->queue[nk], &S->queue[1], (size_t)rest * sizeof(int));
    memcpy(&S->queue[0], kids, (size_t)nk * sizeof(int));
    S->qn = nk + rest;
}

/* ===================== term helpers ===================== */
static Ctx *build_ctx(Arena *ar, Term **ctx, int n) {
    Ctx *c = NULL;
    for (int k = n - 1; k >= 0; k--) c = ctx_cons(ar, ctx[k], c);   /* head = ctx[0] */
    return c;
}
static Term **ctx_push(Arena *ar, Term *ty, Term **ctx, int n) {
    Term **nc = (Term **)arena_alloc(ar, sizeof(Term *) * (n + 1));
    nc[0] = ty; for (int i = 0; i < n; i++) nc[i+1] = ctx[i];
    return nc;
}
static const char **names_push(Arena *ar, const char *nm, const char **names, int n) {
    const char **nn = (const char **)arena_alloc(ar, sizeof(char *) * (n + 1));
    nn[0] = nm; for (int i = 0; i < n; i++) nn[i+1] = names[i];
    return nn;
}
static Term *app_chain(Arena *ar, Term *head, Term **args, int n) {
    for (int i = 0; i < n; i++) head = mk_app(ar, head, args[i]);
    return head;
}

/* Eq A a b  ->  fills A,a,b; returns 1. */
static int eq_parts(Arena *ar, Term *t, Term **A, Term **a, Term **b) {
    t = tm_normalize(ar, t);
    Term *args[4]; int n = 0, cur_is = 0; (void)cur_is;
    Term *cur = t;
    while (cur->kind == T_APP) { if (n < 4) args[n] = cur->b; n++; cur = cur->a; }
    if (cur->kind == T_CONST && strcmp(cur->name, "Eq") == 0 && n == 3) {
        *A = args[2]; *a = args[1]; *b = args[0]; return 1;
    }
    return 0;
}

/* replace occurrences of `a` (shifted) by Var(k), lifting other vars — rewrite */
static Term *abstract(Arena *ar, Term *term, Term *a, int k) {
    if (tm_def_equal(ar, term, tm_shift(ar, a, k, 0))) return mk_var(ar, k);
    switch (term->kind) {
    case T_VAR: return term->i >= k ? mk_var(ar, term->i + 1) : term;
    case T_UNIV: case T_CONST: case T_PROP: case T_META: return term;
    case T_PI:  return mk_pi (ar, abstract(ar, term->a, a, k), abstract(ar, term->b, a, k + 1));
    case T_LAM: return mk_lam(ar, abstract(ar, term->a, a, k), abstract(ar, term->b, a, k + 1));
    case T_APP: return mk_app(ar, abstract(ar, term->a, a, k), abstract(ar, term->b, a, k));
    }
    return term;
}

/* transport P a -> P b along ht : Eq A a b, via the J eliminator */
static Term *transport(Arena *ar, Term *A, Term *a, Term *b, Term *P, Term *target_Pa, Term *ht) {
    Term *A1 = tm_shift(ar, A, 1, 0), *a1 = tm_shift(ar, a, 1, 0);
    Term *eq_a_y = mk_app(ar, mk_app(ar, mk_app(ar, mk_const(ar, "Eq"), A1), a1), mk_var(ar, 0));
    Term *P2 = tm_shift(ar, P, 2, 0), *a2 = tm_shift(ar, a, 2, 0);
    Term *body_pp = mk_pi(ar, mk_app(ar, P2, mk_var(ar, 1)),
                              tm_shift(ar, mk_app(ar, P2, a2), 1, 0));
    Term *pprime = mk_lam(ar, A, mk_lam(ar, eq_a_y, body_pp));
    Term *d = mk_lam(ar, target_Pa, mk_var(ar, 0));
    Term *args[6] = { A, a, pprime, d, b, ht };
    return app_chain(ar, mk_const(ar, "Eq.J"), args, 6);
}

/* ===================== first-order matching ===================== */
typedef struct SubEnt { int id; Term *val; struct SubEnt *next; } SubEnt;
typedef struct { SubEnt *head; Arena *ar; } Subst;
static Term *sub_get(Subst *s, int id) { for (SubEnt *e = s->head; e; e = e->next) if (e->id == id) return e->val; return NULL; }
static void  sub_set(Subst *s, int id, Term *v) {
    SubEnt *e = (SubEnt *)arena_alloc(s->ar, sizeof(SubEnt));
    e->id = id; e->val = v; e->next = s->head; s->head = e;
}
static int has_meta(Term *t) {
    switch (t->kind) {
    case T_META: return 1;
    case T_PI: case T_LAM: case T_APP: return has_meta(t->a) || has_meta(t->b);
    default: return 0;
    }
}
static int match(Arena *ar, Term *pat, Term *term, Subst *s) {
    while (pat->kind == T_META) { Term *v = sub_get(s, pat->i); if (!v) break; pat = v; }
    if (pat->kind == T_META) { sub_set(s, pat->i, term); return 1; }
    if (pat->kind == T_APP && term->kind == T_APP)
        return match(ar, pat->a, term->a, s) && match(ar, pat->b, term->b, s);
    if (pat->kind == T_CONST && term->kind == T_CONST) return strcmp(pat->name, term->name) == 0;
    if (pat->kind == T_VAR  && term->kind == T_VAR)  return pat->i == term->i;
    if (pat->kind == T_UNIV && term->kind == T_UNIV) return pat->i == term->i;
    if (pat->kind == T_PROP && term->kind == T_PROP) return 1;
    if (pat->kind == T_PI   && term->kind == T_PI)
        return match(ar, pat->a, term->a, s) && match(ar, pat->b, term->b, s);
    if (pat->kind == T_LAM  && term->kind == T_LAM)
        return match(ar, pat->a, term->a, s) && match(ar, pat->b, term->b, s);
    if (!has_meta(pat)) return tm_def_equal(ar, pat, term);
    return 0;
}
static Term *inst(Arena *ar, Term *t, Subst *s) {   /* substitute solved metas */
    if (t->kind == T_META) { Term *v = sub_get(s, t->i); return v ? inst(ar, v, s) : t; }
    switch (t->kind) {
    case T_PI:  return mk_pi (ar, inst(ar, t->a, s), inst(ar, t->b, s));
    case T_LAM: return mk_lam(ar, inst(ar, t->a, s), inst(ar, t->b, s));
    case T_APP: return mk_app(ar, inst(ar, t->a, s), inst(ar, t->b, s));
    default: return t;
    }
}

/* ===================== auto (bounded backtracking search) ===================== */
static Term *auto_prove(Arena *ar, Term **ctx, int n, Term *target, int depth);

static Term *auto_apply(Arena *ar, Term *head, Term *hty, Term **ctx, int n, Term *target, int depth) {
    Term *rest = hty, *arg_metas[64], *arg_types[64]; int m = 0;
    while (rest->kind == T_PI && m < 64) {
        Term *meta = mk_meta(ar, m);
        arg_metas[m] = meta; arg_types[m] = rest->a; m++;
        rest = tm_beta(ar, rest->b, meta);
    }
    if (m == 0) return NULL;
    Subst s = { NULL, ar };
    if (!match(ar, rest, tm_normalize(ar, target), &s)) return NULL;
    Term *args[64];
    for (int k = 0; k < m; k++) {
        int id = arg_metas[k]->i;
        Term *v = sub_get(&s, id);
        if (v) { args[k] = v; continue; }
        Term *aty = inst(ar, arg_types[k], &s);
        if (has_meta(aty)) return NULL;                 /* undetermined argument */
        Term *term = auto_prove(ar, ctx, n, aty, depth - 1);
        if (!term) return NULL;
        sub_set(&s, id, term); args[k] = term;
    }
    return app_chain(ar, head, args, m);
}

static Term *auto_prove(Arena *ar, Term **ctx, int n, Term *target, int depth) {
    Term *tn = tm_normalize(ar, target), *A, *a, *b;
    if (eq_parts(ar, tn, &A, &a, &b) && tm_def_equal(ar, a, b))
        return mk_app(ar, mk_app(ar, mk_const(ar, "refl"), A), a);
    for (int i = 0; i < n; i++)
        if (tm_def_equal(ar, tm_shift(ar, ctx[i], i + 1, 0), target)) return mk_var(ar, i);
    if (tn->kind == T_PI) {
        Term *body = auto_prove(ar, ctx_push(ar, tn->a, ctx, n), n + 1, tn->b, depth);
        if (body) return mk_lam(ar, tn->a, body);
    }
    if (depth <= 0) return NULL;
    for (int i = 0; i < n; i++) {
        Term *r = auto_apply(ar, mk_var(ar, i), tm_normalize(ar, tm_shift(ar, ctx[i], i + 1, 0)),
                             ctx, n, target, depth);
        if (r) return r;
    }
    return NULL;
}

/* ===================== instantiate skeleton ===================== */
static Term *instantiate(Session *S, Term *t) {
    if (t->kind == T_META) {
        Term *sol = S->metas[t->i]->solution;
        if (!sol) { snprintf(tactic_err, sizeof tactic_err, "internal: unsolved metavariable"); return NULL; }
        return instantiate(S, sol);
    }
    switch (t->kind) {
    case T_PI:  { Term *x = instantiate(S, t->a); Term *y = x ? instantiate(S, t->b) : NULL; return y ? mk_pi (S->ar, x, y) : NULL; }
    case T_LAM: { Term *x = instantiate(S, t->a); Term *y = x ? instantiate(S, t->b) : NULL; return y ? mk_lam(S->ar, x, y) : NULL; }
    case T_APP: { Term *x = instantiate(S, t->a); Term *y = x ? instantiate(S, t->b) : NULL; return y ? mk_app(S->ar, x, y) : NULL; }
    default: return t;
    }
}

/* ===================== one tactic step ===================== */
static int step(Session *S, Tactic *tac) {
    Arena *ar = S->ar;
    if (S->qn == 0) FAILT("no open goals left for a tactic");
    int gid = S->queue[0];
    Goal *g = S->metas[gid];

    switch (tac->kind) {
    case TAC_INTRO: {
        int cur = gid;
        for (int k = 0; k < tac->nnames; k++) {
            Goal *gc = S->metas[cur];
            Term *t = tm_normalize(ar, gc->target);
            if (t->kind != T_PI) FAILT("intro %s: goal is not a function type", tac->names[k]);
            int child = new_goal(S, ctx_push(ar, t->a, gc->ctx, gc->n),
                                    names_push(ar, tac->names[k], gc->names, gc->n),
                                    gc->n + 1, t->b);
            S->metas[cur]->solution = mk_lam(ar, t->a, mk_meta(ar, child));
            cur = child;
        }
        int one = cur; replace_front(S, &one, 1);
        return 1;
    }
    case TAC_EXACT:
        g->solution = s_to_term_scoped(ar, tac->term, g->names, g->n);
        pop_front(S);
        return 1;

    case TAC_ASSUMPTION:
        for (int i = 0; i < g->n; i++)
            if (tm_def_equal(ar, tm_shift(ar, g->ctx[i], i + 1, 0), g->target)) {
                g->solution = mk_var(ar, i); pop_front(S); return 1;
            }
        FAILT("assumption: no hypothesis matches the goal");

    case TAC_REFL: {
        Term *A, *a, *b;
        if (eq_parts(ar, g->target, &A, &a, &b) && tm_def_equal(ar, a, b)) {
            g->solution = mk_app(ar, mk_app(ar, mk_const(ar, "refl"), A), a);
            pop_front(S); return 1;
        }
        FAILT("refl: goal is not a reflexive equality");
    }
    case TAC_REWRITE: {
        Term *ht = s_to_term_scoped(ar, tac->term, g->names, g->n);
        Term *hty = infer(ar, build_ctx(ar, g->ctx, g->n), ht);
        if (!hty) FAILT("rewrite: %s", infer_err);
        Term *A, *a, *b;
        if (!eq_parts(ar, hty, &A, &a, &b)) FAILT("rewrite: the hypothesis is not an equality");
        Term *body = abstract(ar, g->target, a, 0);
        if (!tm_def_equal(ar, tm_beta(ar, body, a), g->target))
            FAILT("rewrite: could not relocate the term to rewrite");
        Term *P = mk_lam(ar, A, body);
        Term *tr = transport(ar, A, a, b, P, g->target, ht);
        int child = new_goal(S, g->ctx, g->names, g->n, tm_beta(ar, body, b));
        g->solution = mk_app(ar, tr, mk_meta(ar, child));
        replace_front(S, &child, 1);
        return 1;
    }
    case TAC_INDUCTION: {
        Term *t = tm_normalize(ar, g->target);
        if (t->kind != T_PI) FAILT("induction: goal must be `forall (x : D), ...`");
        Term *A = tm_normalize(ar, t->a);
        if (A->kind != T_CONST) FAILT("induction: the bound variable's type is not an inductive");
        char recname[128]; snprintf(recname, sizeof recname, "%s.rec", A->name);
        int np, nc;
        if (!env_recursor_info(recname, &np, &nc)) FAILT("induction: no recursor for %s", A->name);
        if (np != 0) FAILT("induction: parameterised inductives not yet supported");
        Term *rectype = env_const_type(recname);
        Term *P = mk_lam(ar, A, t->b);                 /* motive  fun x => B[x] */
        Term *rt = tm_beta(ar, rectype->b, P);          /* skip motive binder, subst P */
        int *kids = (int *)arena_alloc(ar, sizeof(int) * (nc ? nc : 1));
        Term *tt = rt;
        for (int k = 0; k < nc; k++) {
            if (tt->kind != T_PI) FAILT("induction: malformed recursor type");
            kids[k] = new_goal(S, g->ctx, g->names, g->n, tt->a);
            tt = tm_shift(ar, tt->b, -1, 0);           /* drop the (unused) e_i binder */
        }
        Term *sol = mk_app(ar, mk_const(ar, recname), P);
        for (int k = 0; k < nc; k++) sol = mk_app(ar, sol, mk_meta(ar, kids[k]));
        g->solution = sol;
        replace_front(S, kids, nc);
        return 1;
    }
    case TAC_AUTO: {
        Term *r = auto_prove(ar, g->ctx, g->n, g->target, 6);
        if (!r) FAILT("auto: could not find a proof");
        g->solution = r; pop_front(S); return 1;
    }
    case TAC_APPLY: {
        Term *ft = s_to_term_scoped(ar, tac->term, g->names, g->n);
        Term *rest = infer(ar, build_ctx(ar, g->ctx, g->n), ft);
        if (!rest) FAILT("apply: %s", infer_err);
        rest = tm_normalize(ar, rest);
        int arg_ids[128], na = 0;
        while (rest->kind == T_PI && na < 128) {
            int child = new_goal(S, g->ctx, g->names, g->n, rest->a);
            arg_ids[na++] = child;
            rest = tm_beta(ar, rest->b, mk_meta(ar, child));
        }
        Subst s = { NULL, ar };
        if (!match(ar, rest, tm_normalize(ar, g->target), &s))
            FAILT("apply: the lemma's conclusion does not match the goal");
        int opened[128], no = 0;
        for (int k = 0; k < na; k++) {
            Term *v = sub_get(&s, arg_ids[k]);
            if (v) S->metas[arg_ids[k]]->solution = v;
            else opened[no++] = arg_ids[k];
        }
        Term *sol = ft;
        for (int k = 0; k < na; k++) sol = mk_app(ar, sol, mk_meta(ar, arg_ids[k]));
        g->solution = sol;
        replace_front(S, opened, no);
        return 1;
    }
    }
    FAILT("unknown tactic");
}

Term *run_tactics(Arena *ar, Term *goal, Tactic *tactics, int ntactics) {
    Session S; sess_init(&S, ar);
    int root = new_goal(&S, NULL, NULL, 0, goal);
    q_ensure(&S, 1); S.queue[0] = root; S.qn = 1;
    for (int k = 0; k < ntactics; k++) {
        if (!step(&S, &tactics[k])) { sess_free(&S); return NULL; }
    }
    if (S.qn > 0) { snprintf(tactic_err, sizeof tactic_err, "%d unsolved goal(s) remain", S.qn); sess_free(&S); return NULL; }
    Term *proof = instantiate(&S, mk_meta(ar, root));
    sess_free(&S);
    return proof;
}
