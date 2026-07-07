/* MatyOS-C — the command executor.  Mirrors the Checker in surface.py:
 * runs def/axiom/inductive/example/check/eval against the kernel. */
#ifndef MATYOS_CHECK_H
#define MATYOS_CHECK_H
#include "parse.h"

/* a string set / string->set map, arena-allocated */
typedef struct StrList { char *s; struct StrList *next; } StrList;
typedef struct Oblig   { char *name; Term *type; struct Oblig *next; } Oblig;
typedef struct DepMap  { char *name; StrList *deps; struct DepMap *next; } DepMap;

/* an ordered structured log entry (for --json and project reports) */
typedef struct CheckEvent {
    char *kind, *name, *status, *detail;   /* e.g. kind="proof", status="PROVEN" */
    StrList *deps;
    struct CheckEvent *next;
} CheckEvent;

typedef struct {
    Arena  *ar;
    int     failures;
    Oblig  *obligations;    /* theorem name -> stated (de Bruijn) type      */
    StrList *assumptions;   /* hypothesis/conjecture names (trusted)        */
    StrList *proven;        /* theorem names discharged by a proof          */
    DepMap  *cond_deps;     /* const name -> assumptions it depends on      */
    CheckEvent *events, *events_tail;      /* ordered event log             */
} Checker;

void checker_init(Arena *ar, Checker *c);              /* fresh env + equality prelude */
void checker_exec(Arena *ar, Checker *c, Cmd *cmd, int echo);

/* Run a program's text into an existing checker (for multi-file projects).
 * Returns 0 on success, -1 on parse error (message in parse_err). */
int  checker_run_text(Arena *ar, Checker *c, const char *text, int echo);

/* Print the checker's event log as JSON for a single file. */
void checker_print_json_file(Checker *c, const char *path);

/* Parse and run a whole program in a fresh checker. Returns failure count, or
 * -1 on a parse error (message in parse_err). */
int  elk_run_source(Arena *ar, const char *text, int echo);

#endif /* MATYOS_CHECK_H */
