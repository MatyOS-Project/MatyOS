/* M8b test: project directory checking (scientific-method order across files).
 * Runs the committed fixture project test/proj and expects 0 failures
 * (the proof uses tactics in a .prf, spanning .elk/.thm/.prf/.test files). */
#include "../src/project.h"
#include <stdio.h>

int main(void) {
    Arena *ar = arena_new();
    int failures = project_check(ar, "test/proj");
    arena_free(ar);
    printf("\ntest_project: %s (%d failure%s)\n", failures ? "FAIL" : "OK",
           failures, failures == 1 ? "" : "s");
    return failures ? 1 : 0;
}
