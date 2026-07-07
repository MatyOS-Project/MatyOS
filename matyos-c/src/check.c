#include "check.h"
#include "infer.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---- small arena-backed string set / map ---- */
static int set_has(StrList *s, const char *n) {
    for (; s; s = s->next) if (strcmp(s->s, n) == 0) return 1;
    return 0;
}
static void set_add(Arena *ar, StrList **s, const char *n) {
    if (set_has(*s, n)) return;
    StrList *e = (StrList *)arena_alloc(ar, sizeof(StrList));
    e->s = arena_strdup(ar, n); e->next = *s; *s = e;
}
static StrList *dep_get(Checker *c, const char *name) {
    for (DepMap *m = c->cond_deps; m; m = m->next) if (strcmp(m->name, name) == 0) return m->deps;
    return NULL;
}
static void dep_put(Checker *c, const char *name, StrList *deps) {
    DepMap *m = (DepMap *)arena_alloc(c->ar, sizeof(DepMap));
    m->name = arena_strdup(c->ar, name); m->deps = deps; m->next = c->cond_deps; c->cond_deps = m;
}

/* collect the global constant names referenced in a de Bruijn term */
static void collect_consts(Term *t, Arena *ar, StrList **acc) {
    switch (t->kind) {
    case T_CONST: set_add(ar, acc, t->name); break;
    case T_PI: case T_LAM: case T_APP:
        collect_consts(t->a, ar, acc); collect_consts(t->b, ar, acc); break;
    default: break;
    }
}

/* transitive set of assumptions a proof term relies on (directly or via lemmas
 * that were themselves conditional) — mirrors Checker._deps */
static StrList *compute_deps(Checker *c, Term *term) {
    StrList *consts = NULL; collect_consts(term, c->ar, &consts);
    StrList *deps = NULL;
    for (StrList *p = consts; p; p = p->next) {
        if (set_has(c->assumptions, p->s)) set_add(c->ar, &deps, p->s);
        for (StrList *q = dep_get(c, p->s); q; q = q->next) set_add(c->ar, &deps, q->s);
    }
    return deps;
}

static int cmp_str(const void *a, const void *b) { return strcmp(*(const char **)a, *(const char **)b); }
static void print_deps(StrList *deps) {   /* sorted, comma-separated */
    int n = 0; for (StrList *p = deps; p; p = p->next) n++;
    const char **v = (const char **)malloc(sizeof(char *) * (n ? n : 1));
    int i = 0; for (StrList *p = deps; p; p = p->next) v[i++] = p->s;
    qsort(v, n, sizeof(char *), cmp_str);
    for (i = 0; i < n; i++) printf("%s%s", i ? ", " : "", v[i]);
    free(v);
}

/* ---- term construction helpers ---- */
static SNode *fold(Arena *ar, int is_lam, SParam *bs, int n, SNode *body) {
    SNode *r = body;
    for (int k = n - 1; k >= 0; k--)
        r = is_lam ? s_lam(ar, bs[k].name, bs[k].type, r)
                   : s_pi (ar, bs[k].name, bs[k].type, r);
    return r;
}

void checker_init(Arena *ar, Checker *c) {
    c->ar = ar; c->failures = 0;
    c->obligations = NULL; c->assumptions = NULL; c->proven = NULL; c->cond_deps = NULL;
    env_reset();
    env_setup_equality(ar);
}

void checker_exec(Arena *ar, Checker *c, Cmd *cmd, int echo) {
    switch (cmd->kind) {
    case CMD_DEF: {
        Term *ty = s_to_term(ar, fold(ar, 0, cmd->params, cmd->nparams, cmd->type));
        Term *bd = s_to_term(ar, fold(ar, 1, cmd->params, cmd->nparams, cmd->body));
        if (!env_define(ar, cmd->name, ty, bd)) {
            c->failures++;
            if (echo) printf("def %s   [FAIL: %s]\n", cmd->name, env_err);
        } else {
            dep_put(c, cmd->name, compute_deps(c, bd));   /* a def can be conditional too */
            if (echo) { printf("def %s : ", cmd->name); tm_print(env_const_type(cmd->name)); printf("\n"); }
        }
        break;
    }
    case CMD_AXIOM: {
        Term *ty = s_to_term(ar, cmd->type);
        if (!infer(ar, NULL, ty)) { c->failures++; if (echo) printf("axiom %s   [FAIL: %s]\n", cmd->name, infer_err); break; }
        env_declare_const(cmd->name, ty, NULL);
        if (echo) { printf("axiom %s : ", cmd->name); tm_print(ty); printf("\n"); }
        break;
    }
    case CMD_INDUCTIVE: {
        const char **cnames = (const char **)arena_alloc(ar, sizeof(char *) * (cmd->nctors ? cmd->nctors : 1));
        SNode **ctypes = (SNode **)arena_alloc(ar, sizeof(SNode *) * (cmd->nctors ? cmd->nctors : 1));
        for (int k = 0; k < cmd->nctors; k++) { cnames[k] = cmd->ctors[k].name; ctypes[k] = cmd->ctors[k].ctype; }
        const char *rec = declare_inductive_ctypes(ar, cmd->name, cmd->nparams, cmd->params,
                                                   cmd->type, cmd->nctors, cnames, ctypes);
        if (!rec) { c->failures++; if (echo) printf("inductive %s   [FAIL: %s]\n", cmd->name, env_err); }
        else if (echo) {
            printf("inductive %s : ", cmd->name); tm_print(env_const_type(cmd->name));
            printf("  (%d constructor%s)\n", cmd->nctors, cmd->nctors == 1 ? "" : "s");
        }
        break;
    }
    case CMD_EXAMPLE: {
        Term *tt = s_to_term(ar, cmd->type);
        Term *bt = s_to_term(ar, cmd->body);
        Term *got = infer(ar, NULL, bt);
        if (got && tm_def_equal(ar, got, tt)) {
            if (echo) { printf("example : "); tm_print(tt); printf("   [QED]\n"); }
        } else {
            c->failures++;
            if (echo) { printf("example : "); tm_print(tt);
                printf("   [FAIL: %s]\n", got ? "proof has wrong type" : infer_err); }
        }
        break;
    }
    case CMD_CHECK: {
        Term *t = s_to_term(ar, cmd->body);
        Term *ty = infer(ar, NULL, t);
        if (!ty) { c->failures++; if (echo) printf("check   [FAIL: %s]\n", infer_err); break; }
        if (echo) { printf("check "); tm_print(t); printf(" : "); tm_print(ty); printf("\n"); }
        break;
    }
    case CMD_EVAL: {
        Term *t = s_to_term(ar, cmd->body);
        if (!infer(ar, NULL, t)) { c->failures++; if (echo) printf("eval   [FAIL: %s]\n", infer_err); break; }
        if (echo) { printf("eval "); tm_print(t); printf(" = "); tm_print(tm_normalize(ar, t)); printf("\n"); }
        break;
    }

    /* ----- scientific method ----- */
    case CMD_THEOREM: {
        Term *stmt = s_to_term(ar, fold(ar, 0, cmd->params, cmd->nparams, cmd->type));
        if (!infer(ar, NULL, stmt)) { c->failures++; if (echo) printf("theorem %s   [FAIL: %s]\n", cmd->name, infer_err); break; }
        Oblig *o = (Oblig *)arena_alloc(ar, sizeof(Oblig));
        o->name = arena_strdup(ar, cmd->name); o->type = stmt; o->next = c->obligations; c->obligations = o;
        if (echo) { printf("theorem %s : ", cmd->name); tm_print(stmt); printf("   [stated]\n"); }
        break;
    }
    case CMD_HYP: case CMD_CONJ: {
        const char *kw     = cmd->kind == CMD_HYP ? "hypothesis" : "conjecture";
        const char *status = cmd->kind == CMD_HYP ? "assumed"    : "conjectured";
        Term *t = s_to_term(ar, cmd->type);
        if (!infer(ar, NULL, t)) {
            c->failures++;
            if (echo) printf("%s %s   [FAIL: %s]\n", kw, cmd->name, infer_err);
            break;
        }
        env_declare_const(cmd->name, t, NULL);       /* trusted assumption */
        set_add(ar, &c->assumptions, cmd->name);
        StrList *self = NULL; set_add(ar, &self, cmd->name);
        dep_put(c, cmd->name, self);                 /* depends on itself */
        if (echo) {
            printf("%s %s : ", kw, cmd->name); tm_print(t);
            printf("   [%s (realistic)]\n", status);
        }
        break;
    }
    case CMD_PROOF: {
        Oblig *o = NULL;
        for (Oblig *it = c->obligations; it; it = it->next) if (strcmp(it->name, cmd->name) == 0) { o = it; break; }
        if (!o) { c->failures++; if (echo) printf("proof %s   [FAIL: no theorem '%s' declared]\n", cmd->name, cmd->name); break; }
        Term *bt = s_to_term(ar, cmd->body);
        Term *got = infer(ar, NULL, bt);
        if (got && tm_def_equal(ar, got, o->type)) {
            env_declare_const(cmd->name, o->type, bt);   /* certify + reusable */
            set_add(ar, &c->proven, cmd->name);
            StrList *deps = compute_deps(c, bt);
            dep_put(c, cmd->name, deps);
            if (echo) {
                if (deps) { printf("proof %s   [QED] PROVEN - conditional on: ", cmd->name); print_deps(deps); printf("\n"); }
                else        printf("proof %s   [QED] PROVEN - certified\n", cmd->name);
            }
        } else {
            c->failures++;
            if (echo) printf("proof %s   [FAIL: %s]\n", cmd->name, got ? "proof has wrong type" : infer_err);
        }
        break;
    }
    case CMD_TEST: {
        Term *lt = s_to_term(ar, cmd->body);
        if (!infer(ar, NULL, lt)) { c->failures++; if (echo) printf("test %s   [FAIL: %s]\n", cmd->name, infer_err); break; }
        Term *ln = tm_normalize(ar, lt);
        if (!cmd->rhs) { if (echo) { printf("test %s : ", cmd->name); tm_print(ln); printf("   [ran]\n"); } break; }
        Term *rt = s_to_term(ar, cmd->rhs);
        if (!infer(ar, NULL, rt)) { c->failures++; if (echo) printf("test %s   [FAIL: %s]\n", cmd->name, infer_err); break; }
        if (tm_eq(ln, tm_normalize(ar, rt))) {
            if (echo) { printf("test %s   [PASS] ", cmd->name); tm_print(ln); printf("\n"); }
        } else {
            c->failures++;
            if (echo) { printf("test %s   [FAIL] ", cmd->name); tm_print(ln);
                printf(" != "); tm_print(tm_normalize(ar, rt)); printf("\n"); }
        }
        break;
    }
    default:
        c->failures++;
        if (echo) printf("[FAIL: command not supported yet]\n");
        break;
    }
}

int elk_run_source(Arena *ar, const char *text, int echo) {
    Parser *p = parser_new(ar, text);
    if (!p) return -1;
    Checker c; checker_init(ar, &c);
    for (;;) {
        Cmd cmd;
        if (!parser_next(p, &cmd)) return -1;
        if (cmd.kind == CMD_EOF) break;
        checker_exec(ar, &c, &cmd, echo);
    }
    return c.failures;
}
