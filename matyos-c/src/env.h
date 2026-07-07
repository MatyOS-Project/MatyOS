/* MatyOS-C — the global environment: inductive types, constructors, recursors
 * and definitions.  Mirrors matyos/kernel/inductive.py + the _GLOBALS/_RECURSORS
 * machinery of matyos/kernel/core.py.
 *
 * The kernel TRUSTS the types recorded here and the recursor (iota) reduction
 * rules; everything an inductive declaration generates is re-checked by `infer`
 * before it is admitted (declare_inductive's sanity pass). */
#ifndef MATYOS_ENV_H
#define MATYOS_ENV_H
#include "term.h"

/* ---- environment lifecycle ---- */
void  env_reset(void);                 /* clear all globals; install the reduction hooks */
extern char env_err[256];              /* set when a declaration fails */

/* ---- constants (types, and optional definition body for delta) ---- */
void  env_declare_const(const char *name, Term *type, Term *value /* may be NULL */);
Term *env_const_type(const char *name);   /* NULL if unknown */
Term *env_const_value(const char *name);  /* NULL if unknown or opaque */

/* A checked global definition: verifies `type` is a sort and `value : type`,
 * then registers it so Const(name) delta-reduces to value. Returns 0 on a type
 * error (env_err set), 1 on success. Mirrors core.define. */
int   env_define(Arena *ar, const char *name, Term *type, Term *value);

/* ---- custom eliminator reductions (e.g. the J rule), keyed by constant name.
 *      The generic recursor scheme (declare_inductive) does not cover J. ---- */
typedef Term *(*Reducer)(Arena *ar, Term **spine_args, int nargs);
void  env_register_reducer(const char *name, Reducer fn);

/* Register Eq, refl and the based J eliminator + its reduction rule (mirrors
 * kernel/equality.py:setup_equality). */
void  env_setup_equality(Arena *ar);

/* ---- a tiny named surface-term builder, used only to construct the generated
 *      inductive/constructor/recursor types before lowering to de Bruijn.
 *      (The .elk parser in M5 will lower to de Bruijn the same way.) ---- */
typedef struct SNode SNode;
SNode *s_var(Arena *ar, const char *name);   /* a binder-bound name */
SNode *s_const(Arena *ar, const char *name); /* a global constant */
SNode *s_univ(Arena *ar, int level);
SNode *s_prop(Arena *ar);
SNode *s_pi(Arena *ar, const char *bind, SNode *dom, SNode *cod);
SNode *s_lam(Arena *ar, const char *bind, SNode *dom, SNode *body);
SNode *s_app(Arena *ar, SNode *f, SNode *x);
SNode *s_rec(void);   /* sentinel: a recursive constructor argument (= D params) */

/* Lower a closed named surface term to a de Bruijn kernel term (NULL if it
 * references an unbound name). */
Term *s_to_term(Arena *ar, SNode *n);

/* Lower with a binder scope: names[0] is the innermost binder (de Bruijn #0).
 * Used by the tactic engine so proof terms can reference intro'd hypotheses. */
Term *s_to_term_scoped(Arena *ar, SNode *n, const char **names, int count);

/* If `recname` is a registered recursor, fill *num_params / *nctors and
 * return 1; else return 0. Used by the `induction` tactic. */
int env_recursor_info(const char *recname, int *num_params, int *nctors);

/* ---- declaring an inductive type ---- */
typedef struct { const char *name; SNode *type; } SParam;  /* parameter / telescope entry */
typedef struct { const char *name; SNode *type; } SArg;    /* ctor arg; type may be s_rec() */
typedef struct { const char *name; int nargs; SArg *args; } SCtor;

/* Declare inductive `name` with `nparams` parameters landing in Type<univ>, its
 * constructors, and its recursor (eliminating into Type<motive_univ>).
 * Returns the recursor's name (arena-owned), or NULL on error (env_err set). */
const char *declare_inductive(Arena *ar, const char *name,
                              int nparams, SParam *params, int univ,
                              int nctors, SCtor *ctors, int motive_univ);

/* Surface-driven form used by the .elk front end: each constructor is given by
 * its full type (a surface SNode, e.g. `Nat -> Nat` for succ); this decomposes
 * the Pi-telescope into declare_inductive's arg format (a domain whose head is
 * `name` becomes a recursive REC argument). `sort` must be a Type<u> node. */
const char *declare_inductive_ctypes(Arena *ar, const char *name,
                                     int nparams, SParam *params, SNode *sort,
                                     int nctors, const char **cnames, SNode **ctypes);

#endif /* MATYOS_ENV_H */
