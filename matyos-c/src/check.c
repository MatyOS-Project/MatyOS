#include "check.h"
#include "infer.h"
#include "tactics.h"
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

static void collect_consts(Term *t, Arena *ar, StrList **acc) {
    switch (t->kind) {
    case T_CONST: set_add(ar, acc, t->name); break;
    case T_PI: case T_LAM: case T_APP:
        collect_consts(t->a, ar, acc); collect_consts(t->b, ar, acc); break;
    default: break;
    }
}
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
static const char **deps_sorted(StrList *deps, int *out_n) {
    int n = 0; for (StrList *p = deps; p; p = p->next) n++;
    const char **v = (const char **)malloc(sizeof(char *) * (n ? n : 1));
    int i = 0; for (StrList *p = deps; p; p = p->next) v[i++] = p->s;
    qsort(v, n, sizeof(char *), cmp_str);
    *out_n = n; return v;
}
static void print_deps(StrList *deps) {
    int n; const char **v = deps_sorted(deps, &n);
    for (int i = 0; i < n; i++) printf("%s%s", i ? ", " : "", v[i]);
    free((void *)v);
}

/* ---- event log ---- */
static void emit(Checker *c, const char *kind, const char *name, const char *status,
                 const char *detail, StrList *deps) {
    CheckEvent *e = (CheckEvent *)arena_alloc(c->ar, sizeof(CheckEvent));
    e->kind = arena_strdup(c->ar, kind);
    e->name = arena_strdup(c->ar, name ? name : "");
    e->status = arena_strdup(c->ar, status);
    e->detail = arena_strdup(c->ar, detail ? detail : "");
    e->theory = c->cur_theory; e->deps = deps; e->next = NULL;
    if (c->events_tail) c->events_tail->next = e; else c->events = e;
    c->events_tail = e;
}

/* ---- term construction helpers ---- */
static SNode *fold(Arena *ar, int is_lam, SParam *bs, int n, SNode *body) {
    SNode *r = body;
    for (int k = n - 1; k >= 0; k--)
        r = is_lam ? s_lam(ar, bs[k].name, bs[k].type, r)
                   : s_pi (ar, bs[k].name, bs[k].type, r);
    return r;
}

static Term *term_of(Arena *ar, Cmd *cmd, Term *goal) {
    if (cmd->is_tactic) return run_tactics(ar, goal, cmd->tactics, cmd->ntactics);
    return s_to_term(ar, cmd->body);
}

void checker_init(Arena *ar, Checker *c) {
    c->ar = ar; c->failures = 0;
    c->obligations = NULL; c->assumptions = NULL; c->proven = NULL; c->cond_deps = NULL;
    c->events = NULL; c->events_tail = NULL; c->cur_theory = NULL;
    env_reset();
    env_setup_equality(ar);
}

void checker_exec(Arena *ar, Checker *c, Cmd *cmd, int echo) {
    switch (cmd->kind) {
    case CMD_DEF: {
        Term *ty = s_to_term(ar, fold(ar, 0, cmd->params, cmd->nparams, cmd->type));
        Term *bd = s_to_term(ar, fold(ar, 1, cmd->params, cmd->nparams, cmd->body));
        if (!env_define(ar, cmd->name, ty, bd)) {
            c->failures++; emit(c, "def", cmd->name, "FAILED", env_err, NULL);
            if (echo) printf("def %s   [FAIL: %s]\n", cmd->name, env_err);
        } else {
            dep_put(c, cmd->name, compute_deps(c, bd));
            emit(c, "def", cmd->name, "defined", tm_str(ar, env_const_type(cmd->name)), NULL);
            if (echo) { printf("def %s : ", cmd->name); tm_print(env_const_type(cmd->name)); printf("\n"); }
        }
        break;
    }
    case CMD_AXIOM: {
        Term *ty = s_to_term(ar, cmd->type);
        if (!infer(ar, NULL, ty)) { c->failures++; emit(c, "axiom", cmd->name, "FAILED", infer_err, NULL);
            if (echo) printf("axiom %s   [FAIL: %s]\n", cmd->name, infer_err); break; }
        env_declare_const(cmd->name, ty, NULL);
        emit(c, "axiom", cmd->name, "axiom", tm_str(ar, ty), NULL);
        if (echo) { printf("axiom %s : ", cmd->name); tm_print(ty); printf("\n"); }
        break;
    }
    case CMD_INDUCTIVE: {
        const char **cnames = (const char **)arena_alloc(ar, sizeof(char *) * (cmd->nctors ? cmd->nctors : 1));
        SNode **ctypes = (SNode **)arena_alloc(ar, sizeof(SNode *) * (cmd->nctors ? cmd->nctors : 1));
        for (int k = 0; k < cmd->nctors; k++) { cnames[k] = cmd->ctors[k].name; ctypes[k] = cmd->ctors[k].ctype; }
        const char *rec = declare_inductive_ctypes(ar, cmd->name, cmd->nparams, cmd->params,
                                                   cmd->type, cmd->nctors, cnames, ctypes);
        if (!rec) { c->failures++; emit(c, "inductive", cmd->name, "FAILED", env_err, NULL);
            if (echo) printf("inductive %s   [FAIL: %s]\n", cmd->name, env_err); }
        else {
            emit(c, "inductive", cmd->name, "defined", tm_str(ar, env_const_type(cmd->name)), NULL);
            if (echo) { printf("inductive %s : ", cmd->name); tm_print(env_const_type(cmd->name));
                printf("  (%d constructor%s)\n", cmd->nctors, cmd->nctors == 1 ? "" : "s"); }
        }
        break;
    }
    case CMD_EXAMPLE: {
        Term *tt = s_to_term(ar, cmd->type);
        Term *bt = term_of(ar, cmd, tt);
        if (!bt) { c->failures++; emit(c, "example", "", "FAILED", tactic_err, NULL);
            if (echo) { printf("example : "); tm_print(tt); printf("   [FAIL: tactic: %s]\n", tactic_err); } break; }
        Term *got = infer(ar, NULL, bt);
        if (got && tm_def_equal(ar, got, tt)) {
            emit(c, "example", "", "PROVEN", tm_str(ar, tt), NULL);
            if (echo) { printf("example : "); tm_print(tt); printf("   [QED]\n"); }
        } else {
            c->failures++; emit(c, "example", "", "FAILED", tm_str(ar, tt), NULL);
            if (echo) { printf("example : "); tm_print(tt);
                printf("   [FAIL: %s]\n", got ? "proof has wrong type" : infer_err); }
        }
        break;
    }
    case CMD_CHECK: {
        Term *t = s_to_term(ar, cmd->body);
        Term *ty = infer(ar, NULL, t);
        if (!ty) { c->failures++; emit(c, "check", "", "FAILED", infer_err, NULL);
            if (echo) printf("check   [FAIL: %s]\n", infer_err); break; }
        emit(c, "check", tm_str(ar, t), "ok", tm_str(ar, ty), NULL);
        if (echo) { printf("check "); tm_print(t); printf(" : "); tm_print(ty); printf("\n"); }
        break;
    }
    case CMD_EVAL: {
        Term *t = s_to_term(ar, cmd->body);
        if (!infer(ar, NULL, t)) { c->failures++; emit(c, "eval", "", "FAILED", infer_err, NULL);
            if (echo) printf("eval   [FAIL: %s]\n", infer_err); break; }
        Term *nf = tm_normalize(ar, t);
        emit(c, "eval", tm_str(ar, t), "ok", tm_str(ar, nf), NULL);
        if (echo) { printf("eval "); tm_print(t); printf(" = "); tm_print(nf); printf("\n"); }
        break;
    }

    /* ----- scientific method ----- */
    case CMD_THEOREM: {
        Term *stmt = s_to_term(ar, fold(ar, 0, cmd->params, cmd->nparams, cmd->type));
        if (!infer(ar, NULL, stmt)) { c->failures++; emit(c, "theorem", cmd->name, "FAILED", infer_err, NULL);
            if (echo) printf("theorem %s   [FAIL: %s]\n", cmd->name, infer_err); break; }
        Oblig *o = (Oblig *)arena_alloc(ar, sizeof(Oblig));
        o->name = arena_strdup(ar, cmd->name); o->type = stmt; o->next = c->obligations; c->obligations = o;
        emit(c, "theorem", cmd->name, "stated", tm_str(ar, stmt), NULL);
        if (echo) { printf("theorem %s : ", cmd->name); tm_print(stmt); printf("   [stated]\n"); }
        break;
    }
    case CMD_HYP: case CMD_CONJ: {
        const char *kw     = cmd->kind == CMD_HYP ? "hypothesis" : "conjecture";
        const char *status = cmd->kind == CMD_HYP ? "assumed (realistic)" : "conjectured (realistic)";
        Term *t = s_to_term(ar, cmd->type);
        if (!infer(ar, NULL, t)) {
            c->failures++; emit(c, kw, cmd->name, "FAILED", infer_err, NULL);
            if (echo) printf("%s %s   [FAIL: %s]\n", kw, cmd->name, infer_err);
            break;
        }
        env_declare_const(cmd->name, t, NULL);
        set_add(ar, &c->assumptions, cmd->name);
        StrList *self = NULL; set_add(ar, &self, cmd->name);
        dep_put(c, cmd->name, self);
        emit(c, kw, cmd->name, status, tm_str(ar, t), NULL);
        if (echo) { printf("%s %s : ", kw, cmd->name); tm_print(t); printf("   [%s]\n", status); }
        break;
    }
    case CMD_PROOF: {
        Oblig *o = NULL;
        for (Oblig *it = c->obligations; it; it = it->next) if (strcmp(it->name, cmd->name) == 0) { o = it; break; }
        if (!o) { c->failures++; emit(c, "proof", cmd->name, "FAILED", "no such theorem", NULL);
            if (echo) printf("proof %s   [FAIL: no theorem '%s' declared]\n", cmd->name, cmd->name); break; }
        Term *bt = term_of(ar, cmd, o->type);
        if (!bt) { c->failures++; emit(c, "proof", cmd->name, "FAILED", tactic_err, NULL);
            if (echo) printf("proof %s   [FAIL: tactic: %s]\n", cmd->name, tactic_err); break; }
        Term *got = infer(ar, NULL, bt);
        if (got && tm_def_equal(ar, got, o->type)) {
            env_declare_const(cmd->name, o->type, bt);
            set_add(ar, &c->proven, cmd->name);
            StrList *deps = compute_deps(c, bt);
            dep_put(c, cmd->name, deps);
            if (deps) { emit(c, "proof", cmd->name, "CONDITIONAL", "conditional", deps);
                if (echo) { printf("proof %s   [QED] PROVEN - conditional on: ", cmd->name); print_deps(deps); printf("\n"); } }
            else { emit(c, "proof", cmd->name, "PROVEN", "certified", NULL);
                if (echo) printf("proof %s   [QED] PROVEN - certified\n", cmd->name); }
        } else {
            c->failures++; emit(c, "proof", cmd->name, "FAILED", got ? "wrong type" : infer_err, NULL);
            if (echo) printf("proof %s   [FAIL: %s]\n", cmd->name, got ? "proof has wrong type" : infer_err);
        }
        break;
    }
    case CMD_TEST: {
        Term *lt = s_to_term(ar, cmd->body);
        if (!infer(ar, NULL, lt)) { c->failures++; emit(c, "test", cmd->name, "FAILED", infer_err, NULL);
            if (echo) printf("test %s   [FAIL: %s]\n", cmd->name, infer_err); break; }
        Term *ln = tm_normalize(ar, lt);
        if (!cmd->rhs) { emit(c, "test", cmd->name, "ran", tm_str(ar, ln), NULL);
            if (echo) { printf("test %s : ", cmd->name); tm_print(ln); printf("   [ran]\n"); } break; }
        Term *rt = s_to_term(ar, cmd->rhs);
        if (!infer(ar, NULL, rt)) { c->failures++; emit(c, "test", cmd->name, "FAILED", infer_err, NULL);
            if (echo) printf("test %s   [FAIL: %s]\n", cmd->name, infer_err); break; }
        if (tm_eq(ln, tm_normalize(ar, rt))) {
            emit(c, "test", cmd->name, "passed", tm_str(ar, ln), NULL);
            if (echo) { printf("test %s   [PASS] ", cmd->name); tm_print(ln); printf("\n"); }
        } else {
            c->failures++; emit(c, "test", cmd->name, "failed", tm_str(ar, ln), NULL);
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

int checker_run_text(Arena *ar, Checker *c, const char *text, int echo) {
    Parser *p = parser_new(ar, text);
    if (!p) return -1;
    for (;;) {
        Cmd cmd;
        if (!parser_next(p, &cmd)) return -1;
        if (cmd.kind == CMD_EOF) break;
        checker_exec(ar, c, &cmd, echo);
    }
    return 0;
}

int elk_run_source(Arena *ar, const char *text, int echo) {
    Checker c; checker_init(ar, &c);
    if (checker_run_text(ar, &c, text, echo) < 0) return -1;
    return c.failures;
}

/* ---- JSON output ---- */
static void json_str(const char *s) {
    putchar('"');
    for (; *s; s++) {
        if (*s == '"' || *s == '\\') putchar('\\');
        if (*s == '\n') { printf("\\n"); continue; }
        putchar(*s);
    }
    putchar('"');
}
void checker_print_json_file(Checker *c, const char *path) {
    printf("{\n  \"kind\": \"file\",\n  \"path\": "); json_str(path);
    printf(",\n  \"failures\": %d,\n  \"events\": [", c->failures);
    int first = 1;
    for (CheckEvent *e = c->events; e; e = e->next) {
        printf("%s\n    {\"kind\": ", first ? "" : ","); first = 0;
        json_str(e->kind); printf(", \"name\": "); json_str(e->name);
        printf(", \"status\": "); json_str(e->status);
        printf(", \"detail\": "); json_str(e->detail);
        printf(", \"deps\": [");
        int n; const char **v = deps_sorted(e->deps, &n);
        for (int i = 0; i < n; i++) { if (i) printf(", "); json_str(v[i]); }
        free((void *)v);
        printf("]}");
    }
    printf("%s  ]\n}\n", first ? "" : "\n");
}
