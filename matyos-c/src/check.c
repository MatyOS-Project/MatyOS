#include "check.h"
#include "infer.h"
#include <stdio.h>

static SNode *fold(Arena *ar, int is_lam, SParam *bs, int n, SNode *body) {
    SNode *r = body;
    for (int k = n - 1; k >= 0; k--)
        r = is_lam ? s_lam(ar, bs[k].name, bs[k].type, r)
                   : s_pi (ar, bs[k].name, bs[k].type, r);
    return r;
}

void checker_init(Arena *ar, Checker *c) {
    c->failures = 0;
    env_reset();
    env_setup_equality(ar);   /* Eq / refl / Eq.J available everywhere */
}

void checker_exec(Arena *ar, Checker *c, Cmd *cmd, int echo) {
    switch (cmd->kind) {
    case CMD_DEF: {
        Term *ty = s_to_term(ar, fold(ar, 0, cmd->params, cmd->nparams, cmd->type));
        Term *bd = s_to_term(ar, fold(ar, 1, cmd->params, cmd->nparams, cmd->body));
        if (!env_define(ar, cmd->name, ty, bd)) {
            c->failures++;
            if (echo) printf("def %s   [FAIL: %s]\n", cmd->name, env_err);
        } else if (echo) {
            printf("def %s : ", cmd->name); tm_print(env_const_type(cmd->name)); printf("\n");
        }
        break;
    }
    case CMD_AXIOM: {
        Term *ty = s_to_term(ar, cmd->type);
        Term *s  = infer(ar, NULL, ty);
        if (!s) { c->failures++; if (echo) printf("axiom %s   [FAIL: %s]\n", cmd->name, infer_err); break; }
        env_declare_const(cmd->name, ty, NULL);
        if (echo) { printf("axiom %s : ", cmd->name); tm_print(ty); printf("\n"); }
        break;
    }
    case CMD_INDUCTIVE: {
        const char **cnames = (const char **)arena_alloc(ar, sizeof(char *) * (cmd->nctors ? cmd->nctors : 1));
        SNode **ctypes = (SNode **)arena_alloc(ar, sizeof(SNode *) * (cmd->nctors ? cmd->nctors : 1));
        for (int k = 0; k < cmd->nctors; k++) { cnames[k] = cmd->ctors[k].name; ctypes[k] = cmd->ctors[k].ctype; }
        const char *rec = declare_inductive_ctypes(ar, cmd->name, cmd->nparams, cmd->params,
                                                   cmd->type, cmd->nctors, cnames, ctypes);
        if (!rec) { c->failures++; if (echo) printf("inductive %s   [FAIL: %s]\n", cmd->name, env_err); }
        else if (echo) {
            printf("inductive %s : ", cmd->name); tm_print(env_const_type(cmd->name));
            printf("  (%d constructor%s)\n", cmd->nctors, cmd->nctors == 1 ? "" : "s");
        }
        break;
    }
    case CMD_EXAMPLE: {
        Term *tt = s_to_term(ar, cmd->type);
        Term *bt = s_to_term(ar, cmd->body);
        Term *got = infer(ar, NULL, bt);
        if (got && tm_def_equal(ar, got, tt)) {
            if (echo) { printf("example : "); tm_print(tt); printf("   [QED]\n"); }
        } else {
            c->failures++;
            if (echo) {
                printf("example : "); tm_print(tt);
                printf("   [FAIL: %s]\n", got ? "proof has wrong type" : infer_err);
            }
        }
        break;
    }
    case CMD_CHECK: {
        Term *t = s_to_term(ar, cmd->body);
        Term *ty = infer(ar, NULL, t);
        if (!ty) { c->failures++; if (echo) printf("check   [FAIL: %s]\n", infer_err); break; }
        if (echo) { printf("check "); tm_print(t); printf(" : "); tm_print(ty); printf("\n"); }
        break;
    }
    case CMD_EVAL: {
        Term *t = s_to_term(ar, cmd->body);
        if (!infer(ar, NULL, t)) { c->failures++; if (echo) printf("eval   [FAIL: %s]\n", infer_err); break; }
        if (echo) { printf("eval "); tm_print(t); printf(" = "); tm_print(tm_normalize(ar, t)); printf("\n"); }
        break;
    }
    default:
        c->failures++;
        if (echo) printf("[FAIL: command not supported yet]\n");
        break;
    }
}

int elk_run_source(Arena *ar, const char *text, int echo) {
    Parser *p = parser_new(ar, text);
    if (!p) return -1;
    Checker c; checker_init(ar, &c);
    for (;;) {
        Cmd cmd;
        if (!parser_next(p, &cmd)) return -1;   /* parse error */
        if (cmd.kind == CMD_EOF) break;
        checker_exec(ar, &c, &cmd, echo);
    }
    return c.failures;
}
