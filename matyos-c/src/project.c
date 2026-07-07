#include "project.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <sys/stat.h>

#if defined(_WIN32)
  #define MKDIR(p) mkdir(p)
#else
  #define MKDIR(p) mkdir((p), 0777)
#endif

#define BAR  "=========================================================="
#define DASH "----------------------------------------------------------"

/* ---- file / dir utilities ---- */
static int is_dir(const char *p) {
    struct stat st;
    return stat(p, &st) == 0 && (st.st_mode & S_IFDIR);
}
static char *slurp(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    char *buf = (char *)malloc((size_t)n + 1);
    size_t got = fread(buf, 1, (size_t)n, f); buf[got] = 0;
    fclose(f); return buf;
}
static int ext_phase(const char *fn) {   /* -1 if not a project file */
    const char *dot = strrchr(fn, '.');
    if (!dot) return -1;
    if (!strcmp(dot, ".elk"))  return 0;
    if (!strcmp(dot, ".hyp"))  return 1;
    if (!strcmp(dot, ".thm"))  return 2;
    if (!strcmp(dot, ".test")) return 3;
    if (!strcmp(dot, ".prf"))  return 4;
    return -1;
}

/* ---- discovery ---- */
typedef struct { const char *theory, *rel, *abspath; int phase; } Entry;
typedef struct { Entry *v; int n, cap; Arena *ar; } EntryVec;

static void ev_add(EntryVec *ev, const char *theory, const char *rel, const char *abspath, int phase) {
    if (ev->n == ev->cap) { ev->cap = ev->cap ? ev->cap * 2 : 16; ev->v = realloc(ev->v, sizeof(Entry) * ev->cap); }
    ev->v[ev->n].theory = theory; ev->v[ev->n].rel = rel;
    ev->v[ev->n].abspath = abspath; ev->v[ev->n].phase = phase; ev->n++;
}

static void walk(Arena *ar, size_t rootlen, const char *dir, EntryVec *ev) {
    DIR *d = opendir(dir);
    if (!d) return;
    struct dirent *e;
    while ((e = readdir(d))) {
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, "..")) continue;
        char path[2048];
        snprintf(path, sizeof path, "%s/%s", dir, e->d_name);
        if (is_dir(path)) { walk(ar, rootlen, path, ev); continue; }
        int ph = ext_phase(e->d_name);
        if (ph < 0) continue;
        /* rel = path minus root prefix */
        const char *rel = path + rootlen;
        while (*rel == '/' || *rel == '\\') rel++;
        char *relc = arena_strdup(ar, rel);
        for (char *p = relc; *p; p++) if (*p == '\\') *p = '/';
        /* theory = dirname(rel) or "(root)" */
        char *slash = strrchr(relc, '/');
        const char *theory;
        if (slash) { char *t = arena_strdup(ar, relc); t[slash - relc] = 0; theory = t; }
        else theory = "(root)";
        ev_add(ev, theory, relc, arena_strdup(ar, path), ph);
    }
    closedir(d);
}

static int ecmp(const void *a, const void *b) {
    const Entry *x = a, *y = b;
    if (x->phase != y->phase) return x->phase - y->phase;
    int t = strcmp(x->theory, y->theory);
    return t ? t : strcmp(x->rel, y->rel);
}

/* ---- checker-state queries (Checker struct is public) ---- */
static int sl_has(StrList *s, const char *n) { for (; s; s = s->next) if (!strcmp(s->s, n)) return 1; return 0; }
static StrList *dm_get(DepMap *m, const char *n) { for (; m; m = m->next) if (!strcmp(m->name, n)) return m->deps; return NULL; }
static int sl_len(StrList *s) { int k = 0; for (; s; s = s->next) k++; return k; }

/* an ERROR event appended by the project runner (emit() is file-private) */
static void emit_error(Checker *c, const char *rel, const char *detail) {
    CheckEvent *e = (CheckEvent *)arena_alloc(c->ar, sizeof(CheckEvent));
    e->kind = arena_strdup(c->ar, "error"); e->name = arena_strdup(c->ar, rel);
    e->status = arena_strdup(c->ar, "ERROR"); e->detail = arena_strdup(c->ar, detail);
    e->theory = c->cur_theory; e->deps = NULL; e->next = NULL;
    if (c->events_tail) c->events_tail->next = e; else c->events = e;
    c->events_tail = e;
}

static int cmp_str(const void *a, const void *b) { return strcmp(*(const char **)a, *(const char **)b); }
static void print_deps(StrList *deps) {
    int n = sl_len(deps);
    const char **v = (const char **)malloc(sizeof(char *) * (n ? n : 1));
    int i = 0; for (StrList *p = deps; p; p = p->next) v[i++] = p->s;
    qsort(v, n, sizeof(char *), cmp_str);
    for (i = 0; i < n; i++) printf("%s%s", i ? ", " : "", v[i]);
    free((void *)v);
}

static int is_def_kind(const char *k)  { return !strcmp(k,"def") || !strcmp(k,"inductive") || !strcmp(k,"axiom"); }
static int is_hyp_kind(const char *k)  { return !strcmp(k,"hypothesis") || !strcmp(k,"conjecture"); }

int project_check(Arena *ar, const char *root) {
    EntryVec ev = { NULL, 0, 0, ar };
    walk(ar, strlen(root), root, &ev);
    qsort(ev.v, ev.n, sizeof(Entry), ecmp);

    Checker c; checker_init(ar, &c);
    for (int i = 0; i < ev.n; i++) {
        c.cur_theory = ev.v[i].theory;
        char *text = slurp(ev.v[i].abspath);
        if (!text) { c.failures++; emit_error(&c, ev.v[i].rel, "cannot read file"); continue; }
        if (checker_run_text(ar, &c, text, 0) < 0) { c.failures++; emit_error(&c, ev.v[i].rel, parse_err); }
        free(text);
    }
    c.cur_theory = NULL;

    /* unique theories, sorted */
    const char **theories = (const char **)malloc(sizeof(char *) * (ev.n ? ev.n : 1));
    int nth = 0;
    for (int i = 0; i < ev.n; i++) {
        int seen = 0;
        for (int k = 0; k < nth; k++) if (!strcmp(theories[k], ev.v[i].theory)) { seen = 1; break; }
        if (!seen) theories[nth++] = ev.v[i].theory;
    }
    qsort(theories, nth, sizeof(char *), cmp_str);

    const char *name = strrchr(root, '/') ? strrchr(root, '/') + 1 : root;
    printf("%s\n MatyOS project: %s\n%s\n\n", BAR, name, BAR);

    for (int ti = 0; ti < nth; ti++) {
        const char *th = theories[ti];
        printf("theory: %s\n", th);
        /* definitions */
        int any = 0;
        for (CheckEvent *e = c.events; e; e = e->next)
            if (e->theory && !strcmp(e->theory, th) && is_def_kind(e->kind)) {
                printf(any ? ", %s" : "  definitions: %s", e->name); any = 1;
            }
        if (any) printf("\n");
        /* hypotheses / conjectures */
        any = 0;
        for (CheckEvent *e = c.events; e; e = e->next)
            if (e->theory && !strcmp(e->theory, th) && is_hyp_kind(e->kind)) {
                if (!any) printf("  hypotheses / conjectures (realistic):\n");
                printf("    [%s] %s : %s\n", !strcmp(e->kind,"hypothesis") ? "HYP" : "CONJ", e->name, e->detail);
                any = 1;
            }
        /* theorems */
        any = 0;
        for (CheckEvent *e = c.events; e; e = e->next)
            if (e->theory && !strcmp(e->theory, th) && !strcmp(e->kind, "theorem")) {
                if (!any) printf("  theorems:\n");
                if (sl_has(c.proven, e->name)) {
                    StrList *deps = dm_get(c.cond_deps, e->name);
                    if (deps) { printf("    [PROVEN] %s   (conditional on: ", e->name); print_deps(deps); printf(")\n"); }
                    else printf("    [PROVEN] %s   (certified)\n", e->name);
                } else printf("    [OPEN] %s   (no proof yet)\n", e->name);
                any = 1;
            }
        /* tests */
        any = 0;
        for (CheckEvent *e = c.events; e; e = e->next)
            if (e->theory && !strcmp(e->theory, th) && !strcmp(e->kind, "test")) {
                if (!any) printf("  tests:\n");
                const char *tag = !strcmp(e->status,"passed") ? "PASS" : !strcmp(e->status,"failed") ? "FAIL" : "RAN";
                printf("    [%s] %s\n", tag, e->name); any = 1;
            }
        /* errors */
        any = 0;
        for (CheckEvent *e = c.events; e; e = e->next)
            if (e->theory && !strcmp(e->theory, th) && !strcmp(e->kind, "error")) {
                if (!any) printf("  errors:\n");
                printf("    [ERROR] %s: %s\n", e->name, e->detail); any = 1;
            }
        printf("\n");
    }

    /* summary */
    int proven = sl_len(c.proven), certified = 0;
    for (StrList *p = c.proven; p; p = p->next) if (!dm_get(c.cond_deps, p->s)) certified++;
    int conditional = proven - certified;
    int open_count = 0;
    for (Oblig *o = c.obligations; o; o = o->next) if (!sl_has(c.proven, o->name)) open_count++;
    int tpass = 0, tfail = 0, tran = 0;
    for (CheckEvent *e = c.events; e; e = e->next)
        if (!strcmp(e->kind, "test")) {
            if (!strcmp(e->status, "passed")) tpass++;
            else if (!strcmp(e->status, "failed")) tfail++;
            else if (!strcmp(e->status, "ran")) tran++;
        }
    printf("%s\n Summary\n", DASH);
    printf("   theorems   : %d proven (%d certified, %d conditional), %d open\n",
           proven, certified, conditional, open_count);
    printf("   conjectures: %d (realistic)\n", sl_len(c.assumptions));
    printf("   tests      : %d passed, %d failed, %d ran\n", tpass, tfail, tran);
    const char *status = c.failures ? "FAILURES" : (open_count ? "INCOMPLETE" : "COMPLETE");
    if (open_count && !c.failures) printf("   status     : INCOMPLETE (%d open)  (exit 1)\n", open_count);
    else printf("   status     : %s  (exit %d)\n", status, c.failures ? 1 : 0);
    printf("%s\n", DASH);

    free(theories); free(ev.v);
    return c.failures;
}

/* ---- scaffold (matches engine.py:_SCAFFOLD) ---- */
static void mkpath(const char *path) {   /* create each directory component */
    char buf[1024]; size_t n = 0;
    for (const char *p = path; *p && n < sizeof buf - 1; p++, n++) {
        buf[n] = *p;
        if (*p == '/') { buf[n] = 0; MKDIR(buf); buf[n] = '/'; }
    }
}
static int write_file(const char *dir, const char *rel, const char *content) {
    char path[1024]; snprintf(path, sizeof path, "%s/%s", dir, rel);
    mkpath(path);
    FILE *f = fopen(path, "wb");
    if (!f) return 1;
    fputs(content, f); fclose(f); return 0;
}

int project_scaffold(const char *name) {
    if (is_dir(name)) { fprintf(stderr, "matyos-c: '%s' already exists\n", name); return 1; }
    MKDIR(name);
    int rc = 0;
    rc |= write_file(name, "theories/arithmetic/defs.elk",
        "-- Shared vocabulary for the arithmetic theory.\n"
        "inductive Nat : Type :=\n  | zero : Nat\n  | succ : Nat -> Nat\n\n"
        "def add (m : Nat) (n : Nat) : Nat :=\n"
        "  Nat.rec (fun (_ : Nat) => Nat) n (fun (k : Nat) (ih : Nat) => succ ih) m\n\n"
        "def cong (A : Type) (B : Type) (f : A -> B) (a : A) (b : A) (e : Eq A a b)\n"
        "    : Eq B (f a) (f b) :=\n"
        "  Eq.J A a (fun (x : A) (_ : Eq A a x) => Eq B (f a) (f x)) (refl B (f a)) b e\n");
    rc |= write_file(name, "theories/arithmetic/conjectures.hyp",
        "-- An open conjecture: addition is commutative (assumed, realistic).\n"
        "conjecture add_comm :\n"
        "  forall (a : Nat), forall (b : Nat), Eq Nat (add a b) (add b a)\n");
    rc |= write_file(name, "theories/arithmetic/nat.thm",
        "-- The proposition we aim to establish.\n"
        "theorem add_zero_right : forall (n : Nat), Eq Nat (add n zero) n\n");
    rc |= write_file(name, "theories/arithmetic/nat.test",
        "-- Computational experiments (the kernel runs them).\n"
        "test add_2_3 :\n  add (succ (succ zero)) (succ (succ (succ zero)))\n"
        "  = succ (succ (succ (succ (succ zero))))\n");
    rc |= write_file(name, "theories/arithmetic/nat.prf",
        "-- The proof: induction on n, congruence on the successor.\n"
        "proof add_zero_right :=\n  fun (n : Nat) =>\n"
        "    Nat.rec (fun (m : Nat) => Eq Nat (add m zero) m)\n"
        "            (refl Nat zero)\n"
        "            (fun (k : Nat) (ih : Eq Nat (add k zero) k) =>\n"
        "                cong Nat Nat succ (add k zero) k ih)\n            n\n");
    if (rc) { fprintf(stderr, "matyos-c: failed to write project files\n"); return 1; }
    return 0;
}
