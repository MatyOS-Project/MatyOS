/* MatyOS-C — the trusted type checker (mirrors infer in matyos/kernel/core.py). */
#ifndef MATYOS_INFER_H
#define MATYOS_INFER_H
#include "term.h"

/* Local context: cons-list, head = type of Var 0 (innermost binder). */
typedef struct Ctx Ctx;
struct Ctx { Term *ty; Ctx *rest; };
Ctx *ctx_cons(Arena *ar, Term *ty, Ctx *rest);

extern char infer_err[256];   /* set when infer returns NULL */

/* Infer the type of `t` in context `ctx`. Returns NULL on a type error,
 * with infer_err describing it. */
Term *infer(Arena *ar, Ctx *ctx, Term *t);

/* 1 iff `term` has (definitionally) type `expected` in the empty context. */
int type_check(Arena *ar, Term *term, Term *expected);

#endif /* MATYOS_INFER_H */
