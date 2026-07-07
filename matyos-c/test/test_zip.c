/* M8c test: the .matyos archive — pack round-trip and a sealed build. */
#include "../src/project.h"
#include "../src/zip.h"
#include <stdio.h>
#include <string.h>

static int failures = 0;
static int has_entry(ZipEntry *e, int n, const char *name) {
    for (int i = 0; i < n; i++) if (!strcmp(e[i].name, name)) return 1;
    return 0;
}

int main(void) {
    Arena *ar = arena_new();

    if (project_pack(ar, "test/proj", "build/ztest.matyos") != 0) { printf("  [FAIL] pack\n"); failures++; }
    ZipEntry *e; int n = zip_read(ar, "build/ztest.matyos", &e);
    if (n <= 0) { printf("  [FAIL] zip_read: %s\n", zip_err); failures++; }
    else if (!has_entry(e, n, "theories/arith/defs.elk")) { printf("  [FAIL] packed archive missing defs.elk\n"); failures++; }
    else printf("  [OK] pack + read round-trip (%d entries)\n", n);

    int rc = project_build(ar, "test/proj", "build/zbuilt.matyos", 0);
    if (rc != 0) { printf("  [FAIL] build did not seal a completed project (rc=%d)\n", rc); failures++; }
    int m = zip_read(ar, "build/zbuilt.matyos", &e);
    if (m <= 0 || !has_entry(e, m, "MANIFEST.json") || !has_entry(e, m, "REPORT.txt"))
        { printf("  [FAIL] sealed archive missing MANIFEST.json/REPORT.txt\n"); failures++; }
    else printf("  [OK] build sealed with manifest + report (%d entries)\n", m);

    printf("\ntest_zip: %s (%d failure%s)\n", failures ? "FAIL" : "OK",
           failures, failures == 1 ? "" : "s");
    arena_free(ar);
    return failures ? 1 : 0;
}
