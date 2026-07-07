/* MatyOS-C — the .elk surface syntax: tokenizer + recursive-descent parser.
 * Mirrors matyos/frontend/surface.py.  Parses to the named SNode surface terms
 * (from env.h), which env.c lowers to de Bruijn kernel terms. */
#ifndef MATYOS_PARSE_H
#define MATYOS_PARSE_H
#include "env.h"

typedef enum {
    CMD_DEF, CMD_AXIOM, CMD_INDUCTIVE, CMD_EXAMPLE, CMD_CHECK, CMD_EVAL,
    CMD_THEOREM, CMD_PROOF, CMD_HYP, CMD_CONJ, CMD_TEST, CMD_EOF
} CmdKind;

typedef struct { const char *name; SNode *ctype; } CtorDecl;

typedef enum {
    TAC_INTRO, TAC_EXACT, TAC_ASSUMPTION, TAC_REFL,
    TAC_REWRITE, TAC_INDUCTION, TAC_APPLY, TAC_AUTO
} TacKind;

typedef struct {
    TacKind kind;
    int nnames; const char **names;  /* intro */
    SNode *term;                     /* exact / rewrite / apply */
    const char *var;                 /* induction */
} Tactic;

typedef struct {
    CmdKind kind;
    const char *name;
    int      nparams;  SParam   *params;   /* def / inductive / theorem */
    SNode   *type;                          /* def/axiom/example/theorem type; inductive sort */
    SNode   *body;                          /* def/example body; check/eval/proof/test term */
    int      is_tactic;                     /* body is a tactic block ('by' ... 'qed') */
    int      ntactics; Tactic  *tactics;    /* when is_tactic */
    int      nctors;   CtorDecl *ctors;     /* inductive */
    SNode   *rhs;                           /* test: optional expected value */
} Cmd;

typedef struct Parser Parser;

extern char parse_err[256];

/* Build a parser over `text` (tokenizes; tolerates a leading UTF-8 BOM). */
Parser *parser_new(Arena *ar, const char *text);
int     parser_at_eof(Parser *p);

/* Parse the next top-level command into *out. Returns 1 on success, 0 on error
 * (parse_err set), and sets out->kind == CMD_EOF at end of input. */
int     parser_next(Parser *p, Cmd *out);

#endif /* MATYOS_PARSE_H */
