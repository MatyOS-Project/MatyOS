/* MatyOS-C — the command executor.  Mirrors the Checker in surface.py:
 * runs def/axiom/inductive/example/check/eval against the kernel. */
#ifndef MATYOS_CHECK_H
#define MATYOS_CHECK_H
#include "parse.h"

typedef struct { int failures; } Checker;

void checker_init(Arena *ar, Checker *c);              /* fresh env + equality prelude */
void checker_exec(Arena *ar, Checker *c, Cmd *cmd, int echo);

/* Parse and run a whole program. Returns failure count, or -1 on a parse error
 * (message in parse_err). */
int  elk_run_source(Arena *ar, const char *text, int echo);

#endif /* MATYOS_CHECK_H */
