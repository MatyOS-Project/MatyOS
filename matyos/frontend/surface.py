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
from matyos.kernel.core import (
    N, to_debruijn, infer, normalize, def_equal, pretty, define,
    declare_const, const_type, const_names, Const, TypeError_,
)
from matyos.kernel.inductive import declare_inductive, REC
from matyos.kernel.equality import setup_equality

KEYWORDS = {"fun", "forall", "Type", "Prop",
            "def", "axiom", "inductive", "check", "eval", "example",
            "theorem", "proof", "hypothesis", "conjecture", "test"}
ATOM_STOP = {"fun", "forall", "def", "axiom", "inductive",
             "check", "eval", "example",
             "theorem", "proof", "hypothesis", "conjecture", "test"}
SYMS = [":=", "->", "=>", "(", ")", ":", "=", ",", "|"]  # ':=' / '=>' before '='


class ParseError(Exception):
    pass


# --------------------------------------------------------------------------
# Tokenizer
# --------------------------------------------------------------------------
def tokenize(text):
    toks = []
    if text.startswith("﻿"):  # tolerate a UTF-8 byte-order mark
        text = text[1:]
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n﻿":
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
        # ----- scientific-method commands -----
        if self.at_kw("theorem"):
            self.advance()
            name = self._ident()
            params = self.parse_binders([], required=False)
            pnames = [nm for nm, _ in params]
            self.eat_sym(":")
            ty = self.parse_term(pnames)
            return ("theorem", name, params, ty)
        if self.at_kw("proof"):
            self.advance()
            name = self._ident()
            self.eat_sym(":=")
            body = self.parse_term([])
            return ("proof", name, body)
        if self.at_kw("hypothesis") or self.at_kw("conjecture"):
            kw = self.advance()[1]
            name = self._ident()
            self.eat_sym(":")
            ty = self.parse_term([])
            return (kw, name, ty)
        if self.at_kw("test"):
            self.advance()
            name = self._ident()
            self.eat_sym(":")
            lhs = self.parse_term([])
            rhs = None
            if self.at_sym("="):
                self.eat_sym("=")
                rhs = self.parse_term([])
            return ("test", name, lhs, rhs)
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
# Executor — a stateful Checker shared by single-file checking and projects.
#
# It tracks the scientific-method status of every declaration so a project can
# report:  hypotheses (assumed/realistic) -> theorems (stated) -> tests
# (passed/failed) -> proofs (PROVEN/FAILED) -> theory (verified body).
# --------------------------------------------------------------------------
class Checker:
    def __init__(self):
        setup_equality()  # Eq / refl / Eq.J available everywhere
        self.failures = 0
        self.obligations = {}     # theorem name -> statement term (pending)
        self.proven = set()       # theorem names discharged by a proof
        self.assumptions = {}     # hypothesis/conjecture name -> term (realistic)
        self.cond_deps = {}       # const name -> set of assumptions it depends on
        self.events = []          # ordered structured log (for project reports)

    # -- helpers --
    def _log(self, kind, name, status, detail="", deps=None):
        self.events.append({"kind": kind, "name": name, "status": status,
                            "detail": detail, "deps": sorted(deps or [])})

    def _deps(self, term):
        """Transitive set of assumptions (conjectures/hypotheses) a term relies
        on — directly or via lemmas that were themselves conditional."""
        deps = set()
        for n in const_names(term):
            if n in self.assumptions:
                deps.add(n)
            deps |= self.cond_deps.get(n, set())
        return deps

    def run_text(self, text, echo=True):
        for cmd in Parser(tokenize(text)).parse_program():
            self.exec(cmd, echo)
        return self.failures

    # -- command dispatch --
    def exec(self, cmd, echo=True):
        kind = cmd[0]
        if kind == "def":
            _, name, params, ty, body = cmd
            body_term = to_debruijn(_fold(N.Lam, params, body))
            define(name, to_debruijn(_fold(N.Pi, params, ty)), body_term)
            self.cond_deps[name] = self._deps(body_term)
            self._log("def", name, "defined", pretty(const_type(name)))
            if echo:
                print(f"def {name} : {pretty(const_type(name))}")

        elif kind == "axiom":
            _, name, ty = cmd
            declare_const(name, to_debruijn(ty))
            self._log("axiom", name, "axiom", pretty(const_type(name)))
            if echo:
                print(f"axiom {name} : {pretty(const_type(name))}")

        elif kind == "inductive":
            _, name, params, sort, ctors = cmd
            if not isinstance(sort, N.U):
                raise ParseError(f"inductive '{name}': only 'Type[u]' result "
                                 f"sorts are supported in surface syntax so far")
            decl_ctors = [(cn, _ctor_args(ct, name)) for cn, ct in ctors]
            declare_inductive(name, list(params), sort.level, decl_ctors)
            self._log("inductive", name, "defined", pretty(const_type(name)))
            if echo:
                print(f"inductive {name} : {pretty(const_type(name))}  "
                      f"({len(ctors)} constructors)")

        elif kind in ("hypothesis", "conjecture"):
            _, name, ty = cmd
            t = to_debruijn(ty)
            declare_const(name, t)         # trusted as an assumption
            self.assumptions[name] = t
            self.cond_deps[name] = {name}  # depends on itself
            status = "assumed (realistic)" if kind == "hypothesis" else "conjectured (realistic)"
            self._log(kind, name, status, pretty(t))
            if echo:
                print(f"{kind} {name} : {pretty(t)}   [{status}]")

        elif kind == "theorem":
            _, name, params, ty = cmd
            stmt = to_debruijn(_fold(N.Pi, params, ty))
            self.obligations[name] = stmt
            self._log("theorem", name, "stated", pretty(stmt))
            if echo:
                print(f"theorem {name} : {pretty(stmt)}   [stated]")

        elif kind == "proof":
            _, name, body = cmd
            if name not in self.obligations:
                self.failures += 1
                self._log("proof", name, "FAILED", "no such theorem")
                if echo:
                    print(f"proof {name}   [FAIL: no theorem '{name}' declared]")
            else:
                stmt = self.obligations[name]
                bt = to_debruijn(body)
                got = infer([], bt)
                if def_equal(got, stmt):
                    declare_const(name, stmt, bt)   # certify + reusable
                    self.proven.add(name)
                    deps = self._deps(bt)
                    self.cond_deps[name] = deps
                    if deps:
                        note = " conditional on: " + ", ".join(sorted(deps))
                        self._log("proof", name, "CONDITIONAL", note.strip(), deps)
                        if echo:
                            print(f"proof {name}   [QED] PROVEN -{note}")
                    else:
                        self._log("proof", name, "PROVEN", "certified")
                        if echo:
                            print(f"proof {name}   [QED] PROVEN - certified")
                else:
                    self.failures += 1
                    self._log("proof", name, "FAILED",
                              f"proof has type {pretty(got)}")
                    if echo:
                        print(f"proof {name}   [FAIL: proof has type {pretty(got)}]")

        elif kind == "test":
            _, name, lhs, rhs = cmd
            lt = normalize(to_debruijn(lhs))
            if rhs is None:
                self._log("test", name, "ran", pretty(lt))
                if echo:
                    print(f"test {name} : {pretty(lt)}   [ran]")
            else:
                rt = normalize(to_debruijn(rhs))
                if lt == rt:
                    self._log("test", name, "passed", pretty(lt))
                    if echo:
                        print(f"test {name}   [PASS] {pretty(lt)}")
                else:
                    self.failures += 1
                    self._log("test", name, "failed",
                              f"{pretty(lt)} != {pretty(rt)}")
                    if echo:
                        print(f"test {name}   [FAIL] {pretty(lt)} != {pretty(rt)}")

        elif kind == "example":
            _, ty, body = cmd
            tt, bt = to_debruijn(ty), to_debruijn(body)
            got = infer([], bt)
            if def_equal(got, tt):
                self._log("example", "", "PROVEN", pretty(tt))
                print(f"example : {pretty(tt)}   [QED]")
            else:
                self.failures += 1
                self._log("example", "", "FAILED", pretty(tt))
                print(f"example : {pretty(tt)}   [FAIL: proof has type {pretty(got)}]")

        elif kind == "check":
            _, term = cmd
            t = to_debruijn(term)
            print(f"check {pretty(t)} : {pretty(infer([], t))}")

        elif kind == "eval":
            _, term = cmd
            t = to_debruijn(term)
            print(f"eval {pretty(t)} = {pretty(normalize(t))}")


def run_source(text, echo=True):
    """Execute a program against a fresh checker. Returns the number of failed
    checks (0 on success) so the CLI can exit non-zero when a proof fails."""
    return Checker().run_text(text, echo)


def run_file(path):
    # utf-8-sig transparently strips a leading BOM (common on Windows editors)
    with open(path, "r", encoding="utf-8-sig") as f:
        return run_source(f.read())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m matyos check <file.elk>")
        sys.exit(1)
    run_file(sys.argv[1])
