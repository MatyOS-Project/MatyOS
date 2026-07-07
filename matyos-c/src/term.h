/* MatyOS-C — kernel terms (de Bruijn) and the pure operations on them.
 * A C reimplementation of matyos/kernel/core.py, same architecture. */
#ifndef MATYOS_TERM_H
#define MATYOS_TERM_H
#include <stddef.h>

typedef enum {
    T_VAR,    /* de Bruijn variable, field i = index            */
    T_UNIV,   /* universe Type i, field i = level               */
    T_PROP,   /* the sort Prop                                  */
    T_CONST,  /* global constant, field name                    */
    T_PI,     /* dependent function type: a=domain, b=codomain  */
    T_LAM,    /* lambda: a=domain (arg type), b=body            */
    T_APP     /* application: a=function, b=argument            */
} TermKind;

typedef struct Term Term;
struct Term {
    TermKind kind;
    int i;              /* VAR index / UNIV level */
    const char *name;   /* CONST name (arena-owned) */
    Term *a, *b;
};

/* ---- arena allocator (bump; freed all at once) ---- */
typedef struct Arena Arena;
Arena *arena_new(void);
void   arena_free(Arena *ar);
void  *arena_alloc(Arena *ar, size_t n);
char  *arena_strdup(Arena *ar, const char *s);

/* ---- constructors ---- */
Term *mk_var(Arena *ar, int index);
Term *mk_univ(Arena *ar, int level);
Term *mk_prop(Arena *ar);
Term *mk_const(Arena *ar, const char *name);
Term *mk_pi(Arena *ar, Term *dom, Term *cod);
Term *mk_lam(Arena *ar, Term *dom, Term *body);
Term *mk_app(Arena *ar, Term *fn, Term *arg);

/* ---- pure operations ---- */
Term *tm_shift(Arena *ar, Term *t, int d, int cutoff);
Term *tm_subst(Arena *ar, Term *t, int j, Term *s);
Term *tm_beta(Arena *ar, Term *body, Term *arg);   /* (\.body) arg */
Term *tm_normalize(Arena *ar, Term *t);            /* full beta normal form */
int   tm_eq(Term *x, Term *y);                     /* structural (alpha via de Bruijn) */
int   tm_def_equal(Arena *ar, Term *x, Term *y);   /* equal normal forms */
void  tm_print(Term *t);                           /* debug printer */

/* Delta/iota reduction hooks, installed by the environment (env.c). While NULL
 * (no environment loaded), normalize does pure beta only — the M1/M2 behaviour.
 *  - delta: given a Const, return its unfolding (definition body), or NULL.
 *  - iota:  given an application spine, return the recursor/eliminator
 *           contractum, or NULL if it is not a redex. */
typedef Term *(*TmDeltaHook)(Arena *ar, Term *cst);
typedef Term *(*TmIotaHook)(Arena *ar, Term *app);
extern TmDeltaHook tm_delta_hook;
extern TmIotaHook  tm_iota_hook;

#endif /* MATYOS_TERM_H */
