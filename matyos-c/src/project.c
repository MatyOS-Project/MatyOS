#include "project.h"
#include "zip.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>

#if defined(_WIN32)
  #define MKDIR(p) mkdir(p)
#else
  #define MKDIR(p) mkdir((p), 0777)
#endif

#define BAR  "=========================================================="
#define DASH "----------------------------------------------------------"

/* ---- string builder ---- */
typedef struct { char *buf; size_t len, cap; } SB;
static void sb_init(SB *s) { s->cap = 256; s->len = 0; s->buf = malloc(s->cap); s->buf[0] = 0; }
static void sb_puts(SB *s, const char *p) {
    size_t n = strlen(p);
    if (s->len + n + 1 > s->cap) { while (s->len + n + 1 > s->cap) s->cap *= 2; s->buf = realloc(s->buf, s->cap); }
    memcpy(s->buf + s->len, p, n); s->len += n; s->buf[s->len] = 0;
}
static void sbf(SB *s, const char *fmt, ...) {
    char tmp[2048]; va_list ap; va_start(ap, fmt); vsnprintf(tmp, sizeof tmp, fmt, ap); va_end(ap);
    sb_puts(s, tmp);
}
static void sb_json(SB *s, const char *p) {   /* quoted, escaped */
    sb_puts(s, "\"");
    for (; *p; p++) {
        if (*p == '"' || *p == '\\') { char e[3] = { '\\', *p, 0 }; sb_puts(s, e); }
        else if (*p == '\n') sb_puts(s, "\\n");
        else { char e[2] = { *p, 0 }; sb_puts(s, e); }
    }
    sb_puts(s, "\"");
}

/* ---- fs utilities ---- */
static int is_dir(const char *p) { struct stat st; return stat(p, &st) == 0 && (st.st_mode & S_IFDIR); }
static char *slurp(const char *path, size_t *len) {
    FILE *f = fopen(path, "rb"); if (!f) return NULL;
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    char *buf = (char *)malloc((size_t)n + 1);
    size_t got = fread(buf, 1, (size_t)n, f); buf[got] = 0; fclose(f);
    if (len) *len = got; return buf;
}
static void mkpath(const char *path) {   /* create dir components of a file path */
    char buf[1024]; size_t n = 0;
    for (const char *p = path; *p && n < sizeof buf - 1; p++, n++) {
        buf[n] = *p;
        if (*p == '/') { buf[n] = 0; MKDIR(buf); buf[n] = '/'; }
    }
}
static void mkdirs(const char *dir) { char b[1024]; snprintf(b, sizeof b, "%s/", dir); mkpath(b); }
static void rmtree(const char *dir) {
    DIR *d = opendir(dir);
    if (!d) { remove(dir); return; }
    struct dirent *e;
    while ((e = readdir(d))) {
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, "..")) continue;
        char p[2048]; snprintf(p, sizeof p, "%s/%s", dir, e->d_name);
        if (is_dir(p)) rmtree(p); else remove(p);
    }
    closedir(d);
    rmdir(dir);
}
static const char *basename_of(const char *p) { const char *s = strrchr(p, '/'); return s ? s + 1 : p; }

static int ext_phase(const char *fn) {
    const char *dot = strrchr(fn, '.');
    if (!dot) return -1;
    if (!strcmp(dot, ".elk"))  return 0;
    if (!strcmp(dot, ".hyp"))  return 1;
    if (!strcmp(dot, ".thm"))  return 2;
    if (!strcmp(dot, ".test")) return 3;
    if (!strcmp(dot, ".prf"))  return 4;
    return -1;
}

/* ---- discovery of project (checkable) files ---- */
typedef struct { const char *theory, *rel, *abspath; int phase; } Entry;
typedef struct { Entry *v; int n, cap; } EntryVec;
static void ev_add(EntryVec *ev, const char *th, const char *rel, const char *ap, int ph) {
    if (ev->n == ev->cap) { ev->cap = ev->cap ? ev->cap * 2 : 16; ev->v = realloc(ev->v, sizeof(Entry) * ev->cap); }
    ev->v[ev->n].theory = th; ev->v[ev->n].rel = rel; ev->v[ev->n].abspath = ap; ev->v[ev->n].phase = ph; ev->n++;
}
static void walk(Arena *ar, size_t rootlen, const char *dir, EntryVec *ev) {
    DIR *d = opendir(dir); if (!d) return;
    struct dirent *e;
    while ((e = readdir(d))) {
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, "..")) continue;
        char path[2048]; snprintf(path, sizeof path, "%s/%s", dir, e->d_name);
        if (is_dir(path)) { walk(ar, rootlen, path, ev); continue; }
        int ph = ext_phase(e->d_name); if (ph < 0) continue;
        const char *rel = path + rootlen; while (*rel == '/' || *rel == '\\') rel++;
        char *relc = arena_strdup(ar, rel);
        for (char *p = relc; *p; p++) if (*p == '\\') *p = '/';
        char *slash = strrchr(relc, '/');
        const char *theory;
        if (slash) { char *t = arena_strdup(ar, relc); t[slash - relc] = 0; theory = t; }
        else theory = "(root)";
        ev_add(ev, theory, relc, arena_strdup(ar, path), ph);
    }
    closedir(d);
}
/* walk ALL files (for packing) */
typedef struct { const char *rel, *abspath; } FEnt;
typedef struct { FEnt *v; int n, cap; } FVec;
static void walk_all(Arena *ar, size_t rootlen, const char *dir, FVec *fv) {
    DIR *d = opendir(dir); if (!d) return;
    struct dirent *e;
    while ((e = readdir(d))) {
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, "..")) continue;
        char path[2048]; snprintf(path, sizeof path, "%s/%s", dir, e->d_name);
        if (is_dir(path)) { walk_all(ar, rootlen, path, fv); continue; }
        const char *rel = path + rootlen; while (*rel == '/' || *rel == '\\') rel++;
        char *relc = arena_strdup(ar, rel);
        for (char *p = relc; *p; p++) if (*p == '\\') *p = '/';
        if (fv->n == fv->cap) { fv->cap = fv->cap ? fv->cap * 2 : 16; fv->v = realloc(fv->v, sizeof(FEnt) * fv->cap); }
        fv->v[fv->n].rel = relc; fv->v[fv->n].abspath = arena_strdup(ar, path); fv->n++;
    }
    closedir(d);
}

static int ecmp(const void *a, const void *b) {
    const Entry *x = a, *y = b;
    if (x->phase != y->phase) return x->phase - y->phase;
    int t = strcmp(x->theory, y->theory); return t ? t : strcmp(x->rel, y->rel);
}
static int cmp_str(const void *a, const void *b) { return strcmp(*(const char **)a, *(const char **)b); }

/* ---- checker-state queries ---- */
static int sl_has(StrList *s, const char *n) { for (; s; s = s->next) if (!strcmp(s->s, n)) return 1; return 0; }
static StrList *dm_get(DepMap *m, const char *n) { for (; m; m = m->next) if (!strcmp(m->name, n)) return m->deps; return NULL; }
static int sl_len(StrList *s) { int k = 0; for (; s; s = s->next) k++; return k; }
static int is_def_kind(const char *k) { return !strcmp(k,"def") || !strcmp(k,"inductive") || !strcmp(k,"axiom"); }
static int is_hyp_kind(const char *k) { return !strcmp(k,"hypothesis") || !strcmp(k,"conjecture"); }

static void emit_error(Checker *c, const char *rel, const char *detail) {
    CheckEvent *e = (CheckEvent *)arena_alloc(c->ar, sizeof(CheckEvent));
    e->kind = arena_strdup(c->ar, "error"); e->name = arena_strdup(c->ar, rel);
    e->status = arena_strdup(c->ar, "ERROR"); e->detail = arena_strdup(c->ar, detail);
    e->theory = c->cur_theory; e->deps = NULL; e->next = NULL;
    if (c->events_tail) c->events_tail->next = e; else c->events = e;
    c->events_tail = e;
}
static void sb_deps(SB *s, StrList *deps) {
    int n = sl_len(deps); const char **v = malloc(sizeof(char *) * (n ? n : 1));
    int i = 0; for (StrList *p = deps; p; p = p->next) v[i++] = p->s;
    qsort(v, n, sizeof(char *), cmp_str);
    for (i = 0; i < n; i++) sbf(s, "%s%s", i ? ", " : "", v[i]);
    free((void *)v);
}

/* Run the project and build a text report (+ optional manifest JSON). */
static int analyze(Arena *ar, const char *root, SB *report, SB *mf, int *completed_out) {
    EntryVec ev = { NULL, 0, 0 };
    walk(ar, strlen(root), root, &ev);
    qsort(ev.v, ev.n, sizeof(Entry), ecmp);

    Checker c; checker_init(ar, &c);
    for (int i = 0; i < ev.n; i++) {
        c.cur_theory = ev.v[i].theory;
        size_t len; char *text = slurp(ev.v[i].abspath, &len);
        if (!text) { c.failures++; emit_error(&c, ev.v[i].rel, "cannot read file"); continue; }
        if (checker_run_text(ar, &c, text, 0) < 0) { c.failures++; emit_error(&c, ev.v[i].rel, parse_err); }
        free(text);
    }
    c.cur_theory = NULL;

    const char **theories = malloc(sizeof(char *) * (ev.n ? ev.n : 1));
    int nth = 0;
    for (int i = 0; i < ev.n; i++) {
        int seen = 0;
        for (int k = 0; k < nth; k++) if (!strcmp(theories[k], ev.v[i].theory)) { seen = 1; break; }
        if (!seen) theories[nth++] = ev.v[i].theory;
    }
    qsort(theories, nth, sizeof(char *), cmp_str);

    const char *name = basename_of(root);
    sbf(report, "%s\n MatyOS project: %s\n%s\n\n", BAR, name, BAR);

    /* summary counters */
    int proven = sl_len(c.proven), certified = 0;
    for (StrList *p = c.proven; p; p = p->next) if (!dm_get(c.cond_deps, p->s)) certified++;
    int open_count = 0;
    for (Oblig *o = c.obligations; o; o = o->next) if (!sl_has(c.proven, o->name)) open_count++;
    int tpass = 0, tfail = 0, tran = 0;
    for (CheckEvent *e = c.events; e; e = e->next)
        if (!strcmp(e->kind, "test")) {
            if (!strcmp(e->status, "passed")) tpass++;
            else if (!strcmp(e->status, "failed")) tfail++;
            else if (!strcmp(e->status, "ran")) tran++;
        }
    int completed = (c.failures == 0 && open_count == 0);
    if (completed_out) *completed_out = completed;

    if (mf) {
        sbf(mf, "{\n  \"format\": \"matyos-project/1\",\n  \"name\": ");
        sb_json(mf, name);
        sbf(mf, ",\n  \"completed\": %s,\n", completed ? "true" : "false");
        sbf(mf, "  \"summary\": {\"theorems_proven\": %d, \"certified\": %d, \"conditional\": %d, "
                "\"open\": %d, \"conjectures\": %d, \"tests_passed\": %d, \"tests_failed\": %d, "
                "\"tests_ran\": %d, \"failures\": %d},\n",
                proven, certified, proven - certified, open_count, sl_len(c.assumptions),
                tpass, tfail, tran, c.failures);
        sbf(mf, "  \"theories\": {");
    }

    for (int ti = 0; ti < nth; ti++) {
        const char *th = theories[ti];
        sbf(report, "theory: %s\n", th);
        int any = 0;
        for (CheckEvent *e = c.events; e; e = e->next)
            if (e->theory && !strcmp(e->theory, th) && is_def_kind(e->kind)) {
                sbf(report, any ? ", %s" : "  definitions: %s", e->name); any = 1;
            }
        if (any) sbf(report, "\n");
        any = 0;
        for (CheckEvent *e = c.events; e; e = e->next)
            if (e->theory && !strcmp(e->theory, th) && is_hyp_kind(e->kind)) {
                if (!any) sbf(report, "  hypotheses / conjectures (realistic):\n");
                sbf(report, "    [%s] %s : %s\n", !strcmp(e->kind,"hypothesis") ? "HYP" : "CONJ", e->name, e->detail);
                any = 1;
            }
        any = 0;
        for (CheckEvent *e = c.events; e; e = e->next)
            if (e->theory && !strcmp(e->theory, th) && !strcmp(e->kind, "theorem")) {
                if (!any) sbf(report, "  theorems:\n");
                if (sl_has(c.proven, e->name)) {
                    StrList *deps = dm_get(c.cond_deps, e->name);
                    if (deps) { sbf(report, "    [PROVEN] %s   (conditional on: ", e->name); sb_deps(report, deps); sbf(report, ")\n"); }
                    else sbf(report, "    [PROVEN] %s   (certified)\n", e->name);
                } else sbf(report, "    [OPEN] %s   (no proof yet)\n", e->name);
                any = 1;
            }
        any = 0;
        for (CheckEvent *e = c.events; e; e = e->next)
            if (e->theory && !strcmp(e->theory, th) && !strcmp(e->kind, "test")) {
                if (!any) sbf(report, "  tests:\n");
                const char *tag = !strcmp(e->status,"passed") ? "PASS" : !strcmp(e->status,"failed") ? "FAIL" : "RAN";
                sbf(report, "    [%s] %s\n", tag, e->name); any = 1;
            }
        any = 0;
        for (CheckEvent *e = c.events; e; e = e->next)
            if (e->theory && !strcmp(e->theory, th) && !strcmp(e->kind, "error")) {
                if (!any) sbf(report, "  errors:\n");
                sbf(report, "    [ERROR] %s: %s\n", e->name, e->detail); any = 1;
            }
        sbf(report, "\n");

        if (mf) {   /* theory entry in the manifest */
            sbf(mf, "%s\n    ", ti ? "," : "");
            sb_json(mf, th); sbf(mf, ": {\"theorems\": [");
            int first = 1;
            for (CheckEvent *e = c.events; e; e = e->next)
                if (e->theory && !strcmp(e->theory, th) && !strcmp(e->kind, "theorem")) {
                    const char *st = sl_has(c.proven, e->name) ? "PROVEN" : "OPEN";
                    sbf(mf, "%s{\"name\": ", first ? "" : ", "); first = 0;
                    sb_json(mf, e->name); sbf(mf, ", \"status\": "); sb_json(mf, st); sbf(mf, "}");
                }
            sbf(mf, "]}");
        }
    }
    if (mf) sbf(mf, "\n  }\n}\n");

    sbf(report, "%s\n Summary\n", DASH);
    sbf(report, "   theorems   : %d proven (%d certified, %d conditional), %d open\n",
        proven, certified, proven - certified, open_count);
    sbf(report, "   conjectures: %d (realistic)\n", sl_len(c.assumptions));
    sbf(report, "   tests      : %d passed, %d failed, %d ran\n", tpass, tfail, tran);
    if (open_count && !c.failures) sbf(report, "   status     : INCOMPLETE (%d open)  (exit 1)\n", open_count);
    else sbf(report, "   status     : %s  (exit %d)\n", c.failures ? "FAILURES" : "COMPLETE", c.failures ? 1 : 0);
    sbf(report, "%s\n", DASH);

    free(theories); free(ev.v);
    return c.failures;
}

int project_check(Arena *ar, const char *root) {
    SB report; sb_init(&report);
    int failures = analyze(ar, root, &report, NULL, NULL);
    fputs(report.buf, stdout);
    free(report.buf);
    return failures;
}

/* ---- archives ---- */
int project_pack(Arena *ar, const char *dir, const char *out) {
    char defname[1024];
    if (!out) { snprintf(defname, sizeof defname, "%s.matyos", basename_of(dir)); out = defname; }
    FVec fv = { NULL, 0, 0 };
    walk_all(ar, strlen(dir), dir, &fv);
    Zip *z = zip_create(out);
    if (!z) { fprintf(stderr, "matyos-c: %s\n", zip_err); free(fv.v); return 1; }
    for (int i = 0; i < fv.n; i++) {
        size_t len; char *data = slurp(fv.v[i].abspath, &len);
        if (data) { zip_add(z, fv.v[i].rel, data, len); free(data); }
    }
    zip_close(z);
    free(fv.v);
    printf("Packed -> %s  (%d files)\n", out, fv.n);
    return 0;
}

int project_unpack(Arena *ar, const char *archive, const char *dest) {
    char destbuf[1024];
    if (!dest) {
        const char *b = basename_of(archive);
        size_t n = strlen(b); if (n > 7 && !strcmp(b + n - 7, ".matyos")) n -= 7;
        snprintf(destbuf, sizeof destbuf, "%.*s", (int)n, b); dest = destbuf;
    }
    ZipEntry *ents; int n = zip_read(ar, archive, &ents);
    if (n < 0) { fprintf(stderr, "matyos-c: %s\n", zip_err); return 1; }
    mkdirs(dest);
    for (int i = 0; i < n; i++) {
        char path[2048]; snprintf(path, sizeof path, "%s/%s", dest, ents[i].name);
        mkpath(path);
        FILE *f = fopen(path, "wb");
        if (f) { fwrite(ents[i].data, 1, ents[i].len, f); fclose(f); }
    }
    printf("Unpacked -> %s  (%d files)\n", dest, n);
    return 0;
}

int project_build(Arena *ar, const char *dir, const char *out, int force) {
    SB report, mf; sb_init(&report); sb_init(&mf);
    int completed = 0;
    analyze(ar, dir, &report, &mf, &completed);
    fputs(report.buf, stdout);
    if (!completed && !force) {
        fprintf(stderr, "\nmatyos-c: project is NOT complete (open theorems or failed checks); "
                        "not sealed. Use 'matyos-c build <dir> --force' to archive anyway.\n");
        free(report.buf); free(mf.buf);
        return 1;
    }
    char defname[1024];
    if (!out) { snprintf(defname, sizeof defname, "%s.matyos", basename_of(dir)); out = defname; }
    FVec fv = { NULL, 0, 0 };
    walk_all(ar, strlen(dir), dir, &fv);
    Zip *z = zip_create(out);
    if (!z) { fprintf(stderr, "matyos-c: %s\n", zip_err); free(report.buf); free(mf.buf); free(fv.v); return 1; }
    for (int i = 0; i < fv.n; i++) {
        size_t len; char *data = slurp(fv.v[i].abspath, &len);
        if (data) { zip_add(z, fv.v[i].rel, data, len); free(data); }
    }
    zip_add(z, "MANIFEST.json", mf.buf, mf.len);
    zip_add(z, "REPORT.txt", report.buf, report.len);
    zip_close(z);
    printf("\n%s -> %s\n", completed ? "sealed" : "packed (forced, INCOMPLETE)", out);
    free(report.buf); free(mf.buf); free(fv.v);
    return completed ? 0 : 1;
}

int project_info(Arena *ar, const char *archive) {
    ZipEntry *ents; int n = zip_read(ar, archive, &ents);
    if (n < 0) { fprintf(stderr, "matyos-c: %s\n", zip_err); return 1; }
    for (int i = 0; i < n; i++)
        if (!strcmp(ents[i].name, "MANIFEST.json")) {
            fwrite(ents[i].data, 1, ents[i].len, stdout);
            if (ents[i].len && ents[i].data[ents[i].len - 1] != '\n') printf("\n");
            return 0;
        }
    fprintf(stderr, "matyos-c: no manifest in archive (build it with 'matyos-c build')\n");
    return 1;
}

int project_check_archive(Arena *ar, const char *archive) {
    char tmp[1024]; snprintf(tmp, sizeof tmp, "%s.extract", archive);
    rmtree(tmp);
    if (project_unpack(ar, archive, tmp) != 0) return -1;
    int failures = project_check(ar, tmp);
    rmtree(tmp);
    return failures;
}

/* ---- scaffold ---- */
static int write_file(const char *dir, const char *rel, const char *content) {
    char path[1024]; snprintf(path, sizeof path, "%s/%s", dir, rel);
    mkpath(path);
    FILE *f = fopen(path, "wb"); if (!f) return 1;
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
        "conjecture add_comm :\n"
        "  forall (a : Nat), forall (b : Nat), Eq Nat (add a b) (add b a)\n");
    rc |= write_file(name, "theories/arithmetic/nat.thm",
        "theorem add_zero_right : forall (n : Nat), Eq Nat (add n zero) n\n");
    rc |= write_file(name, "theories/arithmetic/nat.test",
        "test add_2_3 :\n  add (succ (succ zero)) (succ (succ (succ zero)))\n"
        "  = succ (succ (succ (succ (succ zero))))\n");
    rc |= write_file(name, "theories/arithmetic/nat.prf",
        "proof add_zero_right :=\n  fun (n : Nat) =>\n"
        "    Nat.rec (fun (m : Nat) => Eq Nat (add m zero) m)\n"
        "            (refl Nat zero)\n"
        "            (fun (k : Nat) (ih : Eq Nat (add k zero) k) =>\n"
        "                cong Nat Nat succ (add k zero) k ih)\n            n\n");
    if (rc) { fprintf(stderr, "matyos-c: failed to write project files\n"); return 1; }
    return 0;
}
