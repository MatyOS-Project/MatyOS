#include "env.h"
#include "infer.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

char env_err[256];

static char *xstrdup(const char *s) {   /* strdup isn't in C11 */
    size_t n = strlen(s) + 1;
    char *p = (char *)malloc(n);
    memcpy(p, s, n);
    return p;
}

/* ========================================================================
 * Storage: constants and recursor reduction metadata.
 * (Linked lists; small bookkeeping is malloc'd, terms live in the arena.)
 * ===================================================================== */
typedef struct GEntry {
    char *name; Term *type; Term *value; struct GEntry *next;
} GEntry;

typedef struct RecEntry {
    char *rec_name, *inductive;
    int num_params, nctors;
    const char **ctor_names;   /* [nctors]      (arena) */
    int *ctor_nargs;           /* [nctors]      (arena) */
    int **ctor_rec_flags;      /* [nctors][nargs] (arena) */
    struct RecEntry *next;
} RecEntry;

static GEntry   *g_consts = NULL;
static RecEntry *g_recs   = NULL;

static void install_hooks(void);

void env_reset(void) {
    while (g_consts) { GEntry *n = g_consts->next; free(g_consts->name); free(g_consts); g_consts = n; }
    while (g_recs)   { RecEntry *n = g_recs->next; free(g_recs->rec_name); free(g_recs->inductive); free(g_recs); g_recs = n; }
    install_hooks();
}

void env_declare_const(const char *name, Term *type, Term *value) {
    GEntry *e = (GEntry *)malloc(sizeof(GEntry));
    e->name = xstrdup(name); e->type = type; e->value = value;
    e->next = g_consts; g_consts = e;      /* prepend: newest shadows older */
}

static GEntry *find_const(const char *name) {
    for (GEntry *e = g_consts; e; e = e->next)
        if (strcmp(e->name, name) == 0) return e;
    return NULL;
}
Term *env_const_type(const char *name)  { GEntry *e = find_const(name); return e ? e->type  : NULL; }
Term *env_const_value(const char *name) { GEntry *e = find_const(name); return e ? e->value : NULL; }

static RecEntry *find_rec(const char *name) {
    for (RecEntry *r = g_recs; r; r = r->next)
        if (strcmp(r->rec_name, name) == 0) return r;
    return NULL;
}

/* ========================================================================
 * Reduction hooks: delta (unfold definitions) and iota (fire recursors).
 * ===================================================================== */
static Term *delta_hook(Arena *ar, Term *cst) {
    (void)ar;
    return env_const_value(cst->name);   /* NULL => opaque (stays folded) */
}

/* f a b c -> head=f, args=[a,b,c] (arena array) */
static Term *spine(Arena *ar, Term *t, Term ***args, int *n) {
    int count = 0; Term *cur = t;
    while (cur->kind == T_APP) { count++; cur = cur->a; }
    Term **a = (Term **)arena_alloc(ar, sizeof(Term *) * (count ? count : 1));
    int idx = count; cur = t;
    while (cur->kind == T_APP) { a[--idx] = cur->b; cur = cur->a; }
    *args = a; *n = count;
    return cur;
}

/* D.rec params P minors... (c_i cargs...)  ==>  minor_i cargs (interleaving IHs) */
static Term *iota_hook(Arena *ar, Term *app) {
    Term **args; int n;
    Term *head = spine(ar, app, &args, &n);
    if (head->kind != T_CONST) return NULL;
    RecEntry *info = find_rec(head->name);
    if (!info) return NULL;

    int p = info->num_params, nc = info->nctors;
    int expected = p + 1 + nc + 1;      /* params, motive, minors, scrutinee */
    if (n < expected) return NULL;

    Term *scrut = args[p + 1 + nc];
    Term **cargs; int cn;
    Term *chead = spine(ar, scrut, &cargs, &cn);
    if (chead->kind != T_CONST) return NULL;
    int ci = -1;
    for (int i = 0; i < nc; i++)
        if (strcmp(info->ctor_names[i], chead->name) == 0) { ci = i; break; }
    if (ci < 0) return NULL;

    Term *minor = args[p + 1 + ci];
    int *flags = info->ctor_rec_flags[ci];
    Term *result = minor;
    for (int k = p; k < cn; k++) {       /* value args = cargs beyond the params */
        Term *arg = cargs[k];
        result = mk_app(ar, result, arg);
        if (flags[k - p]) {              /* recursive: pass the induction hypothesis */
            Term *ih = head;             /* D.rec params P minors... arg */
            for (int j = 0; j < p + 1 + nc; j++) ih = mk_app(ar, ih, args[j]);
            ih = mk_app(ar, ih, arg);
            result = mk_app(ar, result, ih);
        }
    }
    for (int e = expected; e < n; e++)   /* carry along over-applied arguments */
        result = mk_app(ar, result, args[e]);
    return result;
}

static void install_hooks(void) {
    tm_delta_hook = delta_hook;
    tm_iota_hook  = iota_hook;
}

/* ========================================================================
 * A tiny named surface-term layer + lowering to de Bruijn.
 * Used only to construct the generated inductive/ctor/recursor types.
 * ===================================================================== */
typedef enum { SN_VAR, SN_CONST, SN_UNIV, SN_PROP, SN_PI, SN_LAM, SN_APP } SKind;
struct SNode {
    SKind kind; const char *name; int level; const char *bind; SNode *a, *b;
};

static SNode g_rec_sentinel;   /* unique address = the REC marker */
SNode *s_rec(void) { return &g_rec_sentinel; }

static SNode *sn(Arena *ar, SKind k) {
    SNode *n = (SNode *)arena_alloc(ar, sizeof(SNode));
    n->kind = k; n->name = NULL; n->level = 0; n->bind = NULL; n->a = n->b = NULL;
    return n;
}
SNode *s_var(Arena *ar, const char *name)   { SNode *n = sn(ar, SN_VAR);   n->name = name; return n; }
SNode *s_const(Arena *ar, const char *name) { SNode *n = sn(ar, SN_CONST); n->name = name; return n; }
SNode *s_univ(Arena *ar, int level)         { SNode *n = sn(ar, SN_UNIV);  n->level = level; return n; }
SNode *s_prop(Arena *ar)                    { return sn(ar, SN_PROP); }
SNode *s_pi(Arena *ar, const char *b, SNode *d, SNode *c)  { SNode *n = sn(ar, SN_PI);  n->bind = b; n->a = d; n->b = c; return n; }
SNode *s_lam(Arena *ar, const char *b, SNode *d, SNode *y) { SNode *n = sn(ar, SN_LAM); n->bind = b; n->a = d; n->b = y; return n; }
SNode *s_app(Arena *ar, SNode *f, SNode *x)                { SNode *n = sn(ar, SN_APP); n->a = f; n->b = x; return n; }

typedef struct NameCtx { const char *name; struct NameCtx *rest; } NameCtx;

static Term *to_db(Arena *ar, SNode *n, NameCtx *env) {
    switch (n->kind) {
    case SN_VAR: {
        int idx = 0;
        for (NameCtx *c = env; c; c = c->rest, idx++)
            if (strcmp(c->name, n->name) == 0) return mk_var(ar, idx);
        snprintf(env_err, sizeof env_err, "unbound name in generated type: %s", n->name);
        return NULL;
    }
    case SN_CONST: return mk_const(ar, n->name);
    case SN_UNIV:  return mk_univ(ar, n->level);
    case SN_PROP:  return mk_prop(ar);
    case SN_PI: case SN_LAM: {
        Term *d = to_db(ar, n->a, env); if (!d) return NULL;
        NameCtx e = { n->bind, env };
        Term *c = to_db(ar, n->b, &e); if (!c) return NULL;
        return n->kind == SN_PI ? mk_pi(ar, d, c) : mk_lam(ar, d, c);
    }
    case SN_APP: {
        Term *f = to_db(ar, n->a, env); if (!f) return NULL;
        Term *x = to_db(ar, n->b, env); if (!x) return NULL;
        return mk_app(ar, f, x);
    }
    }
    return NULL;
}

static int s_mentions(SNode *n, const char *name) {
    if (n == s_rec()) return 0;
    switch (n->kind) {
    case SN_CONST: return strcmp(n->name, name) == 0;
    case SN_VAR: case SN_UNIV: case SN_PROP: return 0;
    case SN_PI: case SN_LAM: case SN_APP:
        return s_mentions(n->a, name) || s_mentions(n->b, name);
    }
    return 0;
}

/* nested Pi from a telescope */
static SNode *pi_of(Arena *ar, SParam *tele, int nt, SNode *body) {
    SNode *r = body;
    for (int k = nt - 1; k >= 0; k--) r = s_pi(ar, tele[k].name, tele[k].type, r);
    return r;
}

static char *aprintf(Arena *ar, const char *fmt, ...) {
    char tmp[128]; va_list ap; va_start(ap, fmt);
    vsnprintf(tmp, sizeof tmp, fmt, ap); va_end(ap);
    return arena_strdup(ar, tmp);
}

/* Re-check a generated type: it must itself infer to a sort. */
static int check_is_type(Arena *ar, const char *nm) {
    Term *ty = env_const_type(nm);
    Term *s = ty ? infer(ar, NULL, ty) : NULL;
    if (!s) { snprintf(env_err, sizeof env_err, "generated type of '%s' does not type-check: %s", nm, infer_err); return 0; }
    s = tm_normalize(ar, s);
    if (s->kind != T_UNIV && s->kind != T_PROP) {
        snprintf(env_err, sizeof env_err, "generated type of '%s' is not a sort", nm);
        return 0;
    }
    return 1;
}

const char *declare_inductive(Arena *ar, const char *name,
                              int nparams, SParam *params, int univ,
                              int nctors, SCtor *ctors, int motive_univ) {
    /* 1. strict positivity: no non-REC argument may mention the inductive. */
    for (int ci = 0; ci < nctors; ci++)
        for (int ai = 0; ai < ctors[ci].nargs; ai++) {
            SArg *a = &ctors[ci].args[ai];
            if (a->type != s_rec() && s_mentions(a->type, name)) {
                snprintf(env_err, sizeof env_err,
                    "constructor '%s': argument '%s' mentions '%s' in a "
                    "non-strictly-positive position", ctors[ci].name, a->name, name);
                return NULL;
            }
        }

    /* applied = D p1 ... pm */
    SNode *applied = s_const(ar, name);
    for (int i = 0; i < nparams; i++) applied = s_app(ar, applied, s_var(ar, params[i].name));

    /* 2. type former: D : (params) -> Type univ */
    Term *fdb = to_db(ar, pi_of(ar, params, nparams, s_univ(ar, univ)), NULL);
    if (!fdb) return NULL;
    env_declare_const(name, fdb, NULL);

    /* 3. constructors: c_i : (params)(args) -> D params */
    const char **cnames = (const char **)arena_alloc(ar, sizeof(char *) * (nctors ? nctors : 1));
    int  *cnargs = (int *)arena_alloc(ar, sizeof(int) * (nctors ? nctors : 1));
    int **cflags = (int **)arena_alloc(ar, sizeof(int *) * (nctors ? nctors : 1));

    for (int ci = 0; ci < nctors; ci++) {
        SCtor *c = &ctors[ci];
        cnames[ci] = c->name; cnargs[ci] = c->nargs;
        int *flags = (int *)arena_alloc(ar, sizeof(int) * (c->nargs ? c->nargs : 1));

        SParam tele[256]; int nt = 0;
        for (int i = 0; i < nparams; i++) tele[nt++] = params[i];
        for (int ai = 0; ai < c->nargs; ai++) {
            flags[ai] = (c->args[ai].type == s_rec());
            tele[nt].name = c->args[ai].name;
            tele[nt].type = flags[ai] ? applied : c->args[ai].type;
            nt++;
        }
        cflags[ci] = flags;
        Term *cdb = to_db(ar, pi_of(ar, tele, nt, applied), NULL);
        if (!cdb) return NULL;
        env_declare_const(c->name, cdb, NULL);
    }

    /* 4. recursor: D.rec : (params)(P)(minors)(x) -> P x */
    SParam mt = { "__t", applied };
    SNode *motive_ty = pi_of(ar, &mt, 1, s_univ(ar, motive_univ));

    SParam rtele[256]; int rt = 0;
    for (int i = 0; i < nparams; i++) rtele[rt++] = params[i];
    rtele[rt].name = "__motive"; rtele[rt].type = motive_ty; rt++;

    for (int ci = 0; ci < nctors; ci++) {
        SCtor *c = &ctors[ci];
        SParam minor[256]; int mn = 0;
        for (int ai = 0; ai < c->nargs; ai++) {
            if (c->args[ai].type == s_rec()) {
                minor[mn].name = c->args[ai].name; minor[mn].type = applied; mn++;
                minor[mn].name = aprintf(ar, "__ih_%d_%s", ci, c->args[ai].name);
                minor[mn].type = s_app(ar, s_var(ar, "__motive"), s_var(ar, c->args[ai].name));
                mn++;
            } else {
                minor[mn].name = c->args[ai].name; minor[mn].type = c->args[ai].type; mn++;
            }
        }
        SNode *ctor_applied = s_const(ar, c->name);
        for (int i = 0; i < nparams; i++) ctor_applied = s_app(ar, ctor_applied, s_var(ar, params[i].name));
        for (int ai = 0; ai < c->nargs; ai++) ctor_applied = s_app(ar, ctor_applied, s_var(ar, c->args[ai].name));
        SNode *conclusion = s_app(ar, s_var(ar, "__motive"), ctor_applied);
        rtele[rt].name = aprintf(ar, "__e%d", ci);
        rtele[rt].type = pi_of(ar, minor, mn, conclusion);
        rt++;
    }
    rtele[rt].name = "__x"; rtele[rt].type = applied; rt++;
    SNode *rec_body = s_app(ar, s_var(ar, "__motive"), s_var(ar, "__x"));
    Term *rdb = to_db(ar, pi_of(ar, rtele, rt, rec_body), NULL);
    if (!rdb) return NULL;

    char *rec_name = aprintf(ar, "%s.rec", name);
    env_declare_const(rec_name, rdb, NULL);

    RecEntry *re = (RecEntry *)malloc(sizeof(RecEntry));
    re->rec_name = xstrdup(rec_name); re->inductive = xstrdup(name);
    re->num_params = nparams; re->nctors = nctors;
    re->ctor_names = cnames; re->ctor_nargs = cnargs; re->ctor_rec_flags = cflags;
    re->next = g_recs; g_recs = re;

    /* 5. sanity: every generated type must re-check to a sort. */
    if (!check_is_type(ar, name)) return NULL;
    for (int ci = 0; ci < nctors; ci++)
        if (!check_is_type(ar, ctors[ci].name)) return NULL;
    if (!check_is_type(ar, rec_name)) return NULL;

    return rec_name;
}
