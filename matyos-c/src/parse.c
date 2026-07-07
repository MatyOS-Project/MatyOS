#include "parse.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

char parse_err[256];

/* ---- token stream ---- */
typedef enum { TK_SYM, TK_NUM, TK_ID, TK_EOF } TKind;
typedef struct { TKind kind; char *text; } Token;

struct Parser {
    Arena *ar;
    Token *toks; int ntoks, i;
};

static const char *KEYWORDS[] = {
    "fun","forall","Type","Prop","def","axiom","inductive","check","eval","example",
    "theorem","proof","hypothesis","conjecture","test",
    "by","intro","exact","assumption","refl","rewrite","induction","apply","auto","qed", NULL };
static const char *ATOM_STOP[] = {
    "fun","forall","def","axiom","inductive","check","eval","example",
    "theorem","proof","hypothesis","conjecture","test",
    "by","intro","exact","assumption","refl","rewrite","induction","apply","auto","qed", NULL };
/* multi-char symbols must precede their single-char prefixes */
static const char *SYMS[] = { ":=","->","=>","(",")",":","=",",","|", NULL };

static int in_set(const char *const *set, const char *w) {
    for (int k = 0; set[k]; k++) if (strcmp(set[k], w) == 0) return 1;
    return 0;
}

/* ---- tokenizer ---- */
static int is_id_start(int c) { return isalpha(c) || c == '_'; }
static int is_id_cont(int c)  { return isalnum(c) || c == '_' || c == '\'' || c == '.'; }

static Token *tokenize(Arena *ar, const char *s, int *out_n) {
    int cap = 64, n = 0;
    Token *toks = (Token *)malloc(sizeof(Token) * cap);
    size_t i = 0, len = strlen(s);
    if (len >= 3 && (unsigned char)s[0] == 0xEF && (unsigned char)s[1] == 0xBB
                 && (unsigned char)s[2] == 0xBF) i = 3;   /* skip UTF-8 BOM */
    #define PUSH(k, t) do { if (n == cap) { cap *= 2; toks = realloc(toks, sizeof(Token)*cap); } \
                            toks[n].kind = (k); toks[n].text = (t); n++; } while (0)
    while (i < len) {
        unsigned char c = (unsigned char)s[i];
        if (c == ' ' || c == '\t' || c == '\r' || c == '\n') { i++; continue; }
        if (c == '-' && i + 1 < len && s[i+1] == '-') {      /* line comment */
            while (i < len && s[i] != '\n') i++;
            continue;
        }
        const char *sym = NULL;
        for (int k = 0; SYMS[k]; k++)
            if (strncmp(s + i, SYMS[k], strlen(SYMS[k])) == 0) { sym = SYMS[k]; break; }
        if (sym) { PUSH(TK_SYM, arena_strdup(ar, sym)); i += strlen(sym); continue; }
        if (isdigit(c)) {
            size_t j = i; while (j < len && isdigit((unsigned char)s[j])) j++;
            char *t = (char *)arena_alloc(ar, j - i + 1);
            memcpy(t, s + i, j - i); t[j-i] = 0;
            PUSH(TK_NUM, t); i = j; continue;
        }
        if (is_id_start(c)) {
            size_t j = i; while (j < len && is_id_cont((unsigned char)s[j])) j++;
            char *t = (char *)arena_alloc(ar, j - i + 1);
            memcpy(t, s + i, j - i); t[j-i] = 0;
            PUSH(TK_ID, t); i = j; continue;
        }
        snprintf(parse_err, sizeof parse_err, "unexpected character '%c'", c);
        free(toks); return NULL;
    }
    PUSH(TK_EOF, arena_strdup(ar, ""));
    #undef PUSH
    *out_n = n;
    return toks;
}

Parser *parser_new(Arena *ar, const char *text) {
    int n; Token *toks = tokenize(ar, text, &n);
    if (!toks) return NULL;
    Parser *p = (Parser *)arena_alloc(ar, sizeof(Parser));
    p->ar = ar; p->toks = toks; p->ntoks = n; p->i = 0;
    return p;
}

/* ---- cursor helpers ---- */
static Token cur(Parser *p) { return p->toks[p->i]; }
static int at_sym(Parser *p, const char *s) { Token t = cur(p); return t.kind == TK_SYM && strcmp(t.text, s) == 0; }
static int at_kw (Parser *p, const char *w) { Token t = cur(p); return t.kind == TK_ID  && strcmp(t.text, w) == 0; }
static int at_eof(Parser *p) { return cur(p).kind == TK_EOF; }
int parser_at_eof(Parser *p) { return at_eof(p); }

static int eat_sym(Parser *p, const char *s) {
    if (!at_sym(p, s)) { snprintf(parse_err, sizeof parse_err, "expected '%s', got '%s'", s, cur(p).text); return 0; }
    p->i++; return 1;
}
static const char *ident(Parser *p) {
    Token t = cur(p);
    if (t.kind != TK_ID) { snprintf(parse_err, sizeof parse_err, "expected a name, got '%s'", t.text); return NULL; }
    p->i++; return t.text;
}

/* ---- terms ---- */
static SNode *parse_term(Parser *p);

static SNode *fold_binders(Parser *p, int is_lam, SParam *bs, int nb, SNode *body) {
    SNode *r = body;
    for (int k = nb - 1; k >= 0; k--)
        r = is_lam ? s_lam(p->ar, bs[k].name, bs[k].type, r)
                   : s_pi (p->ar, bs[k].name, bs[k].type, r);
    return r;
}

/* Parse zero+ binder groups `(x y : T)`; returns count (>=0), -1 on error.
 * Backtracks over a '(' that does not open a binder group. */
static int parse_binders(Parser *p, SParam *out, int cap) {
    int nb = 0;
    while (at_sym(p, "(")) {
        int save = p->i;
        p->i++;  /* '(' */
        const char *names[32]; int nn = 0;
        while (cur(p).kind == TK_ID && !in_set(KEYWORDS, cur(p).text)) {
            if (nn < 32) names[nn] = cur(p).text;
            nn++; p->i++;
        }
        if (nn == 0 || !at_sym(p, ":")) { p->i = save; break; }  /* not a binder group */
        p->i++;  /* ':' */
        SNode *ty = parse_term(p);
        if (!ty) return -1;
        if (!eat_sym(p, ")")) return -1;
        for (int k = 0; k < nn; k++) {
            if (nb >= cap) { snprintf(parse_err, sizeof parse_err, "too many binders"); return -1; }
            out[nb].name = names[k]; out[nb].type = ty; nb++;
        }
    }
    return nb;
}

static int starts_atom(Parser *p) {
    Token t = cur(p);
    if (t.kind == TK_SYM) return strcmp(t.text, "(") == 0;
    if (t.kind == TK_ID)  return !in_set(ATOM_STOP, t.text);
    return 0;
}

static SNode *parse_atom(Parser *p) {
    Token t = cur(p);
    if (t.kind == TK_SYM && strcmp(t.text, "(") == 0) {
        p->i++;
        SNode *n = parse_term(p);
        if (!n) return NULL;
        if (!eat_sym(p, ")")) return NULL;
        return n;
    }
    if (t.kind == TK_ID && strcmp(t.text, "Type") == 0) {
        p->i++;
        int lvl = 0;
        if (cur(p).kind == TK_NUM) { lvl = atoi(cur(p).text); p->i++; }
        return s_univ(p->ar, lvl);
    }
    if (t.kind == TK_ID && strcmp(t.text, "Prop") == 0) { p->i++; return s_prop(p->ar); }
    if (t.kind == TK_ID) { p->i++; return s_var(p->ar, t.text); }  /* to_db decides Var vs Const */
    snprintf(parse_err, sizeof parse_err, "expected an expression, got '%s'", t.text);
    return NULL;
}

static SNode *parse_app(Parser *p) {
    SNode *node = parse_atom(p);
    if (!node) return NULL;
    while (starts_atom(p)) {
        SNode *arg = parse_atom(p);
        if (!arg) return NULL;
        node = s_app(p->ar, node, arg);
    }
    return node;
}

static SNode *parse_binding(Parser *p, int is_lam) {
    p->i++;  /* 'fun' / 'forall' */
    SParam bs[64];
    int nb = parse_binders(p, bs, 64);
    if (nb < 0) return NULL;
    if (nb == 0) { snprintf(parse_err, sizeof parse_err, "expected a binder '(x : T)'"); return NULL; }
    if (!eat_sym(p, is_lam ? "=>" : ",")) return NULL;
    SNode *body = parse_term(p);
    if (!body) return NULL;
    return fold_binders(p, is_lam, bs, nb, body);
}

static SNode *parse_term(Parser *p) {
    if (at_kw(p, "fun"))    return parse_binding(p, 1);
    if (at_kw(p, "forall")) return parse_binding(p, 0);
    /* try a dependent Pi:  (x : A) -> B */
    int save = p->i;
    SParam bs[64];
    int nb = parse_binders(p, bs, 64);
    if (nb < 0) return NULL;
    if (nb > 0 && at_sym(p, "->")) {
        p->i++;  /* '->' */
        SNode *body = parse_term(p);
        if (!body) return NULL;
        return fold_binders(p, 0, bs, nb, body);
    }
    p->i = save;  /* not a Pi telescope; parse as application */
    SNode *left = parse_app(p);
    if (!left) return NULL;
    if (at_sym(p, "->")) {              /* non-dependent arrow */
        p->i++;
        SNode *right = parse_term(p);
        if (!right) return NULL;
        return s_pi(p->ar, "_", left, right);
    }
    return left;
}

/* Parse a tactic block `by <tactic>* qed` into out->tactics. Returns 1 on ok. */
static int parse_by(Parser *p, Cmd *out) {
    p->i++;  /* 'by' */
    Tactic *ts = (Tactic *)arena_alloc(p->ar, sizeof(Tactic) * 128);
    int nt = 0;
    while (!at_kw(p, "qed") && !at_eof(p)) {
        if (nt >= 128) { snprintf(parse_err, sizeof parse_err, "too many tactics"); return 0; }
        Tactic *t = &ts[nt];
        memset(t, 0, sizeof *t);
        if (at_kw(p, "intro")) {
            p->i++;
            const char **nm = (const char **)arena_alloc(p->ar, sizeof(char *) * 32);
            int nn = 0;
            while (cur(p).kind == TK_ID && !in_set(KEYWORDS, cur(p).text)) {
                if (nn < 32) nm[nn] = cur(p).text;
                nn++; p->i++;
            }
            if (nn == 0) { snprintf(parse_err, sizeof parse_err, "intro: expected a name"); return 0; }
            t->kind = TAC_INTRO; t->nnames = nn; t->names = nm;
        } else if (at_kw(p, "exact")) {
            p->i++; t->kind = TAC_EXACT; if (!(t->term = parse_term(p))) return 0;
        } else if (at_kw(p, "assumption")) { p->i++; t->kind = TAC_ASSUMPTION; }
        else if (at_kw(p, "refl"))         { p->i++; t->kind = TAC_REFL; }
        else if (at_kw(p, "auto"))         { p->i++; t->kind = TAC_AUTO; }
        else if (at_kw(p, "rewrite")) {
            p->i++; t->kind = TAC_REWRITE; if (!(t->term = parse_term(p))) return 0;
        } else if (at_kw(p, "apply")) {
            p->i++; t->kind = TAC_APPLY; if (!(t->term = parse_term(p))) return 0;
        } else if (at_kw(p, "induction")) {
            p->i++; t->kind = TAC_INDUCTION; if (!(t->var = ident(p))) return 0;
        } else {
            snprintf(parse_err, sizeof parse_err, "expected a tactic, got '%s'", cur(p).text);
            return 0;
        }
        nt++;
    }
    if (!at_kw(p, "qed")) { snprintf(parse_err, sizeof parse_err, "tactic block must end with 'qed'"); return 0; }
    p->i++;  /* 'qed' */
    out->is_tactic = 1; out->ntactics = nt; out->tactics = ts;
    return 1;
}

/* ---- commands ---- */
int parser_next(Parser *p, Cmd *out) {
    memset(out, 0, sizeof *out);
    if (at_eof(p)) { out->kind = CMD_EOF; return 1; }

    if (at_kw(p, "def")) {
        p->i++;
        out->kind = CMD_DEF;
        if (!(out->name = ident(p))) return 0;
        SParam *bs = (SParam *)arena_alloc(p->ar, sizeof(SParam) * 64);
        int nb = parse_binders(p, bs, 64);
        if (nb < 0) return 0;
        out->nparams = nb; out->params = bs;
        if (!eat_sym(p, ":")) return 0;
        if (!(out->type = parse_term(p))) return 0;
        if (!eat_sym(p, ":=")) return 0;
        if (at_kw(p, "by")) { snprintf(parse_err, sizeof parse_err, "tactic blocks arrive in M7"); return 0; }
        if (!(out->body = parse_term(p))) return 0;
        return 1;
    }
    if (at_kw(p, "axiom")) {
        p->i++;
        out->kind = CMD_AXIOM;
        if (!(out->name = ident(p))) return 0;
        if (!eat_sym(p, ":")) return 0;
        if (!(out->type = parse_term(p))) return 0;
        return 1;
    }
    if (at_kw(p, "inductive")) {
        p->i++;
        out->kind = CMD_INDUCTIVE;
        if (!(out->name = ident(p))) return 0;
        SParam *bs = (SParam *)arena_alloc(p->ar, sizeof(SParam) * 64);
        int nb = parse_binders(p, bs, 64);
        if (nb < 0) return 0;
        out->nparams = nb; out->params = bs;
        if (!eat_sym(p, ":")) return 0;
        if (!(out->type = parse_term(p))) return 0;   /* the sort */
        if (!eat_sym(p, ":=")) return 0;
        CtorDecl *cs = (CtorDecl *)arena_alloc(p->ar, sizeof(CtorDecl) * 64);
        int nc = 0;
        while (at_sym(p, "|")) {
            p->i++;
            if (nc >= 64) { snprintf(parse_err, sizeof parse_err, "too many constructors"); return 0; }
            if (!(cs[nc].name = ident(p))) return 0;
            if (!eat_sym(p, ":")) return 0;
            if (!(cs[nc].ctype = parse_term(p))) return 0;
            nc++;
        }
        out->nctors = nc; out->ctors = cs;
        return 1;
    }
    if (at_kw(p, "example")) {
        p->i++;
        out->kind = CMD_EXAMPLE;
        if (!eat_sym(p, ":")) return 0;
        if (!(out->type = parse_term(p))) return 0;
        if (!eat_sym(p, ":=")) return 0;
        if (at_kw(p, "by")) return parse_by(p, out);
        if (!(out->body = parse_term(p))) return 0;
        return 1;
    }
    if (at_kw(p, "check")) {
        p->i++;
        out->kind = CMD_CHECK;
        if (!(out->body = parse_term(p))) return 0;
        return 1;
    }
    if (at_kw(p, "eval")) {
        p->i++;
        out->kind = CMD_EVAL;
        if (!(out->body = parse_term(p))) return 0;
        return 1;
    }
    /* ----- scientific-method commands ----- */
    if (at_kw(p, "theorem")) {
        p->i++;
        out->kind = CMD_THEOREM;
        if (!(out->name = ident(p))) return 0;
        SParam *bs = (SParam *)arena_alloc(p->ar, sizeof(SParam) * 64);
        int nb = parse_binders(p, bs, 64);
        if (nb < 0) return 0;
        out->nparams = nb; out->params = bs;
        if (!eat_sym(p, ":")) return 0;
        if (!(out->type = parse_term(p))) return 0;
        return 1;
    }
    if (at_kw(p, "proof")) {
        p->i++;
        out->kind = CMD_PROOF;
        if (!(out->name = ident(p))) return 0;
        if (!eat_sym(p, ":=")) return 0;
        if (at_kw(p, "by")) return parse_by(p, out);
        if (!(out->body = parse_term(p))) return 0;
        return 1;
    }
    if (at_kw(p, "hypothesis") || at_kw(p, "conjecture")) {
        out->kind = at_kw(p, "hypothesis") ? CMD_HYP : CMD_CONJ;
        p->i++;
        if (!(out->name = ident(p))) return 0;
        if (!eat_sym(p, ":")) return 0;
        if (!(out->type = parse_term(p))) return 0;
        return 1;
    }
    if (at_kw(p, "test")) {
        p->i++;
        out->kind = CMD_TEST;
        if (!(out->name = ident(p))) return 0;
        if (!eat_sym(p, ":")) return 0;
        if (!(out->body = parse_term(p))) return 0;
        if (at_sym(p, "=")) { p->i++; if (!(out->rhs = parse_term(p))) return 0; }
        return 1;
    }
    snprintf(parse_err, sizeof parse_err, "expected a command, got '%s'", cur(p).text);
    return 0;
}
