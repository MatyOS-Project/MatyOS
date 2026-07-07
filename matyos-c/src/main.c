/* MatyOS-C command-line interface:  matyos-c check <file.elk> */
#include "check.h"
#include "project.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

static int path_is_dir(const char *p) {
    struct stat st; return stat(p, &st) == 0 && (st.st_mode & S_IFDIR);
}

static char *read_file(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "matyos-c: cannot open %s\n", path); return NULL; }
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *buf = (char *)malloc((size_t)n + 1);
    size_t got = fread(buf, 1, (size_t)n, f);
    buf[got] = 0;
    fclose(f);
    return buf;
}

static int ends_with(const char *s, const char *suf) {
    size_t n = strlen(s), m = strlen(suf);
    return n >= m && strcmp(s + n - m, suf) == 0;
}

static int cmd_check(const char *path, int as_json) {
    if (path_is_dir(path)) {                 /* a project directory */
        Arena *ar = arena_new();
        int failures = project_check(ar, path);
        arena_free(ar);
        return failures > 0 ? 1 : (failures < 0 ? 2 : 0);
    }
    if (ends_with(path, ".matyos")) {        /* a sealed archive */
        Arena *ar = arena_new();
        int failures = project_check_archive(ar, path);
        arena_free(ar);
        return failures > 0 ? 1 : (failures < 0 ? 2 : 0);
    }
    char *text = read_file(path);
    if (!text) return 2;
    Arena *ar = arena_new();
    int rc;
    if (as_json) {
        Checker c; checker_init(ar, &c);
        if (checker_run_text(ar, &c, text, 0) < 0) {
            fprintf(stderr, "matyos-c: parse error: %s\n", parse_err); rc = 2;
        } else {
            checker_print_json_file(&c, path);
            rc = c.failures ? 1 : 0;
        }
    } else {
        int failures = elk_run_source(ar, text, 1);
        if (failures < 0) {
            fprintf(stderr, "matyos-c: parse error: %s\n", parse_err); rc = 2;
        } else {
            printf("\n%s: %d failure%s\n", failures ? "FAIL" : "OK",
                   failures, failures == 1 ? "" : "s");
            rc = failures ? 1 : 0;
        }
    }
    arena_free(ar);
    free(text);
    return rc;
}

int main(int argc, char **argv) {
    /* collect flags */
    int as_json = 0, force = 0;
    const char *cmd = NULL, *a1 = NULL, *a2 = NULL;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--json")) as_json = 1;
        else if (!strcmp(argv[i], "--force")) force = 1;
        else if (!cmd) cmd = argv[i];
        else if (!a1) a1 = argv[i];
        else if (!a2) a2 = argv[i];
    }
    if (!cmd) { fprintf(stderr, "usage: matyos-c <check|new|pack|unpack|build|info|version> ...\n"); return 1; }
    if (!strcmp(cmd, "version")) { printf("matyos-c 0.1 (C rewrite)\n"); return 0; }
    if (!strcmp(cmd, "check")) { if (!a1) { fprintf(stderr, "usage: matyos-c check [--json] <path>\n"); return 2; } return cmd_check(a1, as_json); }
    if (!strcmp(cmd, "new")) {
        if (!a1) { fprintf(stderr, "usage: matyos-c new <name>\n"); return 2; }
        if (project_scaffold(a1)) return 1;
        printf("Created project '%s'.  Try:  matyos-c check %s\n", a1, a1);
        return 0;
    }
    if (!strcmp(cmd, "pack") || !strcmp(cmd, "unpack") || !strcmp(cmd, "build") || !strcmp(cmd, "info")) {
        if (!a1) { fprintf(stderr, "usage: matyos-c %s <path> [out]\n", cmd); return 2; }
        Arena *ar = arena_new(); int rc;
        if (!strcmp(cmd, "pack"))       rc = project_pack(ar, a1, a2);
        else if (!strcmp(cmd, "unpack")) rc = project_unpack(ar, a1, a2);
        else if (!strcmp(cmd, "build"))  rc = project_build(ar, a1, a2, force);
        else                             rc = project_info(ar, a1);
        arena_free(ar);
        return rc;
    }
    /* bare path -> check it */
    if (path_is_dir(cmd) || ends_with(cmd, ".elk") || ends_with(cmd, ".matyos")) return cmd_check(cmd, as_json);
    fprintf(stderr, "matyos-c: unknown command '%s'\n", cmd);
    return 2;
}
