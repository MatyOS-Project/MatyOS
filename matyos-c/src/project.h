/* MatyOS-C — projects: the scientific method as a file system.
 * Mirrors matyos/project/engine.py.  A project is a directory of files whose
 * extension gives their role (.elk/.hyp/.thm/.test/.prf); they run in
 * scientific-method order through one shared kernel session. */
#ifndef MATYOS_PROJECT_H
#define MATYOS_PROJECT_H
#include "check.h"

/* Check a project directory: run all files (definitions -> hypotheses ->
 * theorems -> tests -> proofs) and print a report. Returns failure count,
 * or -1 on I/O / parse error. */
int project_check(Arena *ar, const char *root);

/* Scaffold a new project directory `name` with a sample theory. Returns 0 on
 * success, 1 if it already exists / on error. */
int project_scaffold(const char *name);

#endif /* MATYOS_PROJECT_H */
