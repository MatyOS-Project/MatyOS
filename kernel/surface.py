"""
Surface syntax for the proof language (Phase C3).

A small, readable concrete syntax that parses to the kernel's terms and is
checked by the trusted kernel. Proofs now live in text files, not Python.

Grammar (informal):

    term    := 'fun' binders '=>' term
             | 'forall' binders ',' term
             | binders '->' term                 -- dependent function type
             | app ('->' term)?                   -- non-dependent arrow
    app     := atom atom*
    atom    := ident | 'Type' number? | 'Prop' | '(' term ')'
    binders := ('(' ident+ ':' term ')')+

Top-level commands:

    def NAME binders* : TYPE := TERM
    axiom NAME : TYPE
    inductive NAME params* : Type[u] := | C1 : T1 | C2 : T2 ...
    example : TYPE := TERM           -- check an anonymous proof
    check TERM                       -- print the inferred type
    eval  TERM                       -- print the normal form

Comments start with `--`. Identifiers may contain dots (so `Nat.rec`, `Eq.J`).
"""

import sys
from kernel.core import (
    N, to_debruijn, infer, normalize, def_equal, pretty, define,
    declare_const, const_type, Const, TypeError_,
)
from kernel.inductive import declare_inductive, REC
from kernel.equality import setup_equality

KEYWORDS = {"fun", "forall", "Type", "Prop",
            "def", "axiom", "inductive", "check", "eval", "example"}
ATOM_STOP = {"fun", "forall", "def", "axiom", "inductive",
             "check", "eval", "example"}
SYMS = [":=", "->", "=>", "(", ")", ":", ",", "|"]


class ParseError(Exception):
    pass


# --------------------------------------------------------------------------
# Tokenizer
# --------------------------------------------------------------------------
def tokenize(text):
    toks = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c == "-" and i + 1 < n and text[i + 1] == "-":  # line comment
            while i < n and text[i] != "\n":
                i += 1
            continue
        # multi-char / single-char symbols
        matched = None
        for s in SYMS:
            if text.startswith(s, i):
                matched = s
                break
        if matched:
            toks.append(("sym", matched))
            i += len(matched)
            continue
        if c.isdigit():
            j = i
            while j < n and text[j].isdigit():
                j += 1
            toks.append(("num", text[i:j]))
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (text[j].isalnum() or text[j] in "_'."):
                j += 1
            toks.append(("id", text[i:j]))
            i = j
            continue
        raise ParseError(f"unexpected character {c!r} at offset {i}")
    toks.append(("eof", ""))
    return toks


# --------------------------------------------------------------------------
# Parser  (produces N.* surface terms; to_debruijn finalises de Bruijn indices)
# --------------------------------------------------------------------------
class Parser:
    def __init__(self, toks):
        self.toks = toks
        self.i = 0

    def peek(self):
        return self.toks[self.i]

    def advance(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def at_sym(self, s):
        k, v = self.peek()
        return k == "sym" and v == s

    def at_kw(self, w):
        k, v = self.peek()
        return k == "id" and v == w

    def eat_sym(self, s):
        if not self.at_sym(s):
            raise ParseError(f"expected '{s}', got {self.peek()}")
        self.advance()

    # ----- terms -----
    def parse_term(self, scope):
        if self.at_kw("fun"):
            return self.parse_binding(scope, "fun")
        if self.at_kw("forall"):
            return self.parse_binding(scope, "forall")
        # try dependent Pi:  (x : A) -> B
        save = self.i
        binders = self.parse_binders(scope, required=False)
        if binders and self.at_sym("->"):
            self.eat_sym("->")
            inner = scope + [nm for nm, _ in binders]
            body = self.parse_term(inner)
            return _fold(N.Pi, binders, body)
        self.i = save
        left = self.parse_app(scope)
        if self.at_sym("->"):
            self.eat_sym("->")
            right = self.parse_term(scope)
            return N.Arrow(left, right)
        return left

    def parse_binding(self, scope, kind):
        self.advance()  # 'fun' or 'forall'
        binders = self.parse_binders(scope, required=True)
        if kind == "fun":
            self.eat_sym("=>")
        else:
            self.eat_sym(",")
        inner = scope + [nm for nm, _ in binders]
        body = self.parse_term(inner)
        return _fold(N.Lam if kind == "fun" else N.Pi, binders, body)

    def parse_binders(self, scope, required):
        groups = []
        cur = list(scope)
        while self.at_sym("("):
            save = self.i
            self.eat_sym("(")
            names = []
            while self.peek()[0] == "id" and self.peek()[1] not in KEYWORDS:
                names.append(self.advance()[1])
            if not names or not self.at_sym(":"):
                self.i = save           # not a binder group -> stop
                break
            self.eat_sym(":")
            ty = self.parse_term(cur)
            self.eat_sym(")")
            for nm in names:
                groups.append((nm, ty))
                cur.append(nm)
        if required and not groups:
            raise ParseError(f"expected a binder '(x : T)', got {self.peek()}")
        return groups

    def parse_app(self, scope):
        node = self.parse_atom(scope)
        while self._starts_atom():
            node = N.App(node, self.parse_atom(scope))
        return node

    def _starts_atom(self):
        k, v = self.peek()
        if k == "sym":
            return v == "("
        if k == "id":
            return v not in ATOM_STOP
        return False

    def parse_atom(self, scope):
        k, v = self.peek()
        if k == "sym" and v == "(":
            self.eat_sym("(")
            node = self.parse_term(scope)
            self.eat_sym(")")
            return node
        if k == "id" and v == "Type":
            self.advance()
            if self.peek()[0] == "num":
                lvl = int(self.advance()[1])
            else:
                lvl = 0
            return N.U(lvl)
        if k == "id" and v == "Prop":
            self.advance()
            return N.Prop()
        if k == "id":
            self.advance()
            return N.Var(v) if v in scope else N.Const(v)
        raise ParseError(f"expected an expression, got {self.peek()}")

    # ----- commands -----
    def parse_program(self):
        cmds = []
        while self.peek()[0] != "eof":
            cmds.append(self.parse_command())
        return cmds

    def _ident(self):
        k, v = self.peek()
        if k != "id":
            raise ParseError(f"expected a name, got {self.peek()}")
        self.advance()
        return v

    def parse_command(self):
        if self.at_kw("def"):
            self.advance()
            name = self._ident()
            params = self.parse_binders([], required=False)
            pnames = [nm for nm, _ in params]
            self.eat_sym(":")
            ty = self.parse_term(pnames)
            self.eat_sym(":=")
            body = self.parse_term(pnames)
            return ("def", name, params, ty, body)
        if self.at_kw("axiom"):
            self.advance()
            name = self._ident()
            self.eat_sym(":")
            ty = self.parse_term([])
            return ("axiom", name, ty)
        if self.at_kw("example"):
            self.advance()
            self.eat_sym(":")
            ty = self.parse_term([])
            self.eat_sym(":=")
            body = self.parse_term([])
            return ("example", ty, body)
        if self.at_kw("check"):
            self.advance()
            return ("check", self.parse_term([]))
        if self.at_kw("eval"):
            self.advance()
            return ("eval", self.parse_term([]))
        if self.at_kw("inductive"):
            self.advance()
            name = self._ident()
            params = self.parse_binders([], required=False)
            pnames = [nm for nm, _ in params]
            self.eat_sym(":")
            sort = self.parse_term(pnames)
            self.eat_sym(":=")
            ctors = []
            while self.at_sym("|"):
                self.eat_sym("|")
                cname = self._ident()
                self.eat_sym(":")
                ctype = self.parse_term(pnames)
                ctors.append((cname, ctype))
            return ("inductive", name, params, sort, ctors)
        raise ParseError(f"expected a command, got {self.peek()}")


def _fold(ctor, binders, body):
    result = body
    for nm, ty in reversed(binders):
        result = ctor(nm, ty, result)
    return result


# --------------------------------------------------------------------------
# Decompose a constructor type into declare_inductive's argument format.
# --------------------------------------------------------------------------
def _spine_head_name(node):
    while isinstance(node, N.App):
        node = node.func
    return node.name if isinstance(node, N.Const) else None


def _ctor_args(ctype, indname):
    args = []
    t = ctype
    while isinstance(t, (N.Pi, N.Arrow)):
        if isinstance(t, N.Pi):
            name, dom, t = t.name, t.domain, t.codomain
        else:
            name, dom, t = f"a{len(args)}", t.domain, t.codomain
        if _spine_head_name(dom) == indname:
            args.append((name, REC))
        else:
            args.append((name, dom))
    return args


# --------------------------------------------------------------------------
# Executor
# --------------------------------------------------------------------------
def run_source(text, echo=True):
    setup_equality()  # make Eq / refl / Eq.J available to every file
    cmds = Parser(tokenize(text)).parse_program()
    for cmd in cmds:
        kind = cmd[0]
        if kind == "def":
            _, name, params, ty, body = cmd
            type_term = to_debruijn(_fold(N.Pi, params, ty))
            body_term = to_debruijn(_fold(N.Lam, params, body))
            define(name, type_term, body_term)
            if echo:
                print(f"def {name} : {pretty(const_type(name))}")
        elif kind == "axiom":
            _, name, ty = cmd
            declare_const(name, to_debruijn(ty))
            if echo:
                print(f"axiom {name} : {pretty(const_type(name))}")
        elif kind == "inductive":
            _, name, params, sort, ctors = cmd
            if not isinstance(sort, N.U):
                raise ParseError(f"inductive '{name}': only 'Type[u]' result "
                                 f"sorts are supported in surface syntax so far")
            decl_params = [(nm, ty) for nm, ty in params]
            decl_ctors = [(cn, _ctor_args(ct, name)) for cn, ct in ctors]
            declare_inductive(name, decl_params, sort.level, decl_ctors)
            if echo:
                print(f"inductive {name} : {pretty(const_type(name))}  "
                      f"({len(ctors)} constructors)")
        elif kind == "example":
            _, ty, body = cmd
            tt, bt = to_debruijn(ty), to_debruijn(body)
            got = infer([], bt)
            if def_equal(got, tt):
                print(f"example : {pretty(tt)}   [QED]")
            else:
                print(f"example : {pretty(tt)}   [FAIL: proof has type {pretty(got)}]")
        elif kind == "check":
            _, term = cmd
            t = to_debruijn(term)
            print(f"check {pretty(t)} : {pretty(infer([], t))}")
        elif kind == "eval":
            _, term = cmd
            t = to_debruijn(term)
            print(f"eval {pretty(t)} = {pretty(normalize(t))}")


def run_file(path):
    with open(path, "r", encoding="utf-8") as f:
        run_source(f.read())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m kernel.surface <file.elk>")
        sys.exit(1)
    run_file(sys.argv[1])
