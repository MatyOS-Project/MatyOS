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

static int cmd_check(const char *path) {
    char *text = read_file(path);
    if (!text) return 2;
    Arena *ar = arena_new();
    int failures = elk_run_source(ar, text, 1);
    int rc;
    if (failures < 0) {
        fprintf(stderr, "matyos-c: parse error: %s\n", parse_err);
        rc = 2;
    } else {
        printf("\n%s: %d failure%s\n", failures ? "FAIL" : "OK",
               failures, failures == 1 ? "" : "s");
        rc = failures ? 1 : 0;
    }
    arena_free(ar);
    free(text);
    return rc;
}

int main(int argc, char **argv) {
    if (argc >= 3 && strcmp(argv[1], "check") == 0) return cmd_check(argv[2]);
    if (argc == 2) return cmd_check(argv[1]);          /* matyos-c <file.elk> */
    if (argc >= 2 && strcmp(argv[1], "version") == 0) { printf("matyos-c 0.1 (C rewrite)\n"); return 0; }
    fprintf(stderr, "usage: matyos-c check <file.elk>\n");
    return 1;
}
