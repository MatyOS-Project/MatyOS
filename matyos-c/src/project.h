/* MatyOS-C — projects: the scientific method as a file system.
 * Mirrors matyos/project/engine.py.  A project is a directory of files whose
 * extension gives their role (.elk/.hyp/.thm/.test/.prf); they run in
 * scientific-method order through one shared kernel session.  A whole project
 * packs into a single `.matyos` archive (a zip). */
#ifndef MATYOS_PROJECT_H
#define MATYOS_PROJECT_H
#include "check.h"

/* Check a project directory and print a report. Returns failures, or -1. */
int project_check(Arena *ar, const char *root);

/* Check a sealed `.matyos` archive (extract to a temp dir, then check). */
int project_check_archive(Arena *ar, const char *archive);

/* Scaffold a new project directory with a sample theory. 0 ok, 1 on error. */
int project_scaffold(const char *name);

/* Pack a directory into a `.matyos` (no checking). out NULL -> <dir>.matyos. */
int project_pack(Arena *ar, const char *dir, const char *out);

/* Extract a `.matyos` archive. dest NULL -> archive basename. */
int project_unpack(Arena *ar, const char *archive, const char *dest);

/* Seal a COMPLETED project into a `.matyos` (embeds MANIFEST.json + REPORT.txt).
 * Returns 0 if sealed, 1 if incomplete (and not forced) or on error. */
int project_build(Arena *ar, const char *dir, const char *out, int force);

/* Print a sealed archive's embedded MANIFEST.json. 0 ok, 1 if none. */
int project_info(Arena *ar, const char *archive);

#endif /* MATYOS_PROJECT_H */
