/* MatyOS-C command-line interface:  matyos-c check <file.elk> */
#include "check.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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

static int cmd_check(const char *path, int as_json) {
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
    int as_json = 0;
    const char *path = NULL, *cmd = NULL;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--json") == 0) as_json = 1;
        else if (!cmd && (strcmp(argv[i], "check") == 0 || strcmp(argv[i], "version") == 0)) cmd = argv[i];
        else if (!path) path = argv[i];
    }
    if (cmd && strcmp(cmd, "version") == 0) { printf("matyos-c 0.1 (C rewrite)\n"); return 0; }
    if (cmd && strcmp(cmd, "check") == 0 && path) return cmd_check(path, as_json);
    if (!cmd && path) return cmd_check(path, as_json);   /* matyos-c <file.elk> */
    fprintf(stderr, "usage: matyos-c check [--json] <file.elk>\n");
    return 1;
}
