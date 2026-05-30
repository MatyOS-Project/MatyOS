"""
Surface-syntax parser & file-checker test suite (MatyOS / El proof language).

Covers matyos.frontend.surface: the tokenizer, the term/command parser, and the
end-to-end executor `run_source` / `run_file` that drives the trusted kernel in
matyos.kernel.core.

Author: Ahmed Hafdi
"""

import os
import pytest

from matyos.frontend.surface import (
    tokenize, Parser, run_source, run_file, ParseError,
)
from matyos.kernel.core import (
    N, to_debruijn, infer, reset_environment, Pi as KPi, Univ, PropSort,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Every executor test mutates the global kernel environment; isolate each one.
@pytest.fixture(autouse=True)
def _fresh_env():
    reset_environment()
    yield
    reset_environment()


def pterm(s):
    """Parse a single surface term in an empty scope."""
    return Parser(tokenize(s)).parse_term([])


# ===========================================================================
# Tokenizer
# ===========================================================================
class TestTokenize:
    def test_ends_in_eof(self):
        assert tokenize("x")[-1] == ("eof", "")
        assert tokenize("")[-1] == ("eof", "")

    def test_line_comment_skipped(self):
        toks = tokenize("x -- this is a comment\n y")
        assert toks == [("id", "x"), ("id", "y"), ("eof", "")]

    def test_comment_to_end_of_input(self):
        # a trailing comment with no newline still terminates cleanly
        toks = tokenize("a -- trailing")
        assert toks == [("id", "a"), ("eof", "")]

    def test_multichar_symbols(self):
        toks = tokenize("a := b -> c => d")
        assert toks == [
            ("id", "a"), ("sym", ":="),
            ("id", "b"), ("sym", "->"),
            ("id", "c"), ("sym", "=>"),
            ("id", "d"), ("eof", ""),
        ]

    def test_multichar_not_split_into_single(self):
        # ':=' must not become ':' then '='; '->' must not become '-' then '>'.
        assert ("sym", ":=") in tokenize("x := y")
        assert ("sym", ":") not in tokenize("x := y")
        assert ("sym", "->") in tokenize("A -> B")

    def test_dotted_identifiers_are_single_tokens(self):
        assert tokenize("Nat.rec") == [("id", "Nat.rec"), ("eof", "")]
        assert tokenize("Eq.J") == [("id", "Eq.J"), ("eof", "")]
        toks = tokenize("Nat.rec Eq.J")
        assert toks == [("id", "Nat.rec"), ("id", "Eq.J"), ("eof", "")]

    def test_primes_and_underscores_in_idents(self):
        assert tokenize("x'_0") == [("id", "x'_0"), ("eof", "")]

    def test_numbers(self):
        toks = tokenize("Type 42")
        assert toks == [("id", "Type"), ("num", "42"), ("eof", "")]
        assert tokenize("0")[0] == ("num", "0")

    def test_unexpected_character_raises(self):
        with pytest.raises(ParseError):
            tokenize("a @ b")


# ===========================================================================
# Term parsing
# ===========================================================================
class TestParseTerms:
    def test_lambda(self):
        t = pterm("fun (x : A) => x")
        assert isinstance(t, N.Lam)
        assert t.name == "x"
        assert isinstance(t.domain, N.Const) and t.domain.name == "A"
        # `x` is bound, so it parses as a Var (not a Const)
        assert isinstance(t.body, N.Var) and t.body.name == "x"

    def test_dependent_pi(self):
        t = pterm("(x : A) -> B")
        assert isinstance(t, N.Pi)
        assert t.name == "x"
        assert isinstance(t.domain, N.Const) and t.domain.name == "A"
        assert isinstance(t.codomain, N.Const) and t.codomain.name == "B"

    def test_nondependent_arrow(self):
        t = pterm("A -> B")
        assert isinstance(t, N.Arrow)
        assert isinstance(t.domain, N.Const) and t.domain.name == "A"
        assert isinstance(t.codomain, N.Const) and t.codomain.name == "B"

    def test_arrow_is_right_associative(self):
        # A -> B -> C  parses as  A -> (B -> C)
        t = pterm("A -> B -> C")
        assert isinstance(t, N.Arrow)
        assert isinstance(t.domain, N.Const) and t.domain.name == "A"
        assert isinstance(t.codomain, N.Arrow)
        assert t.codomain.domain.name == "B"
        assert t.codomain.codomain.name == "C"

    def test_application_left_associative(self):
        # f a b  parses as  (f a) b
        t = pterm("f a b")
        assert isinstance(t, N.App)
        assert isinstance(t.arg, N.Const) and t.arg.name == "b"
        assert isinstance(t.func, N.App)
        assert t.func.func.name == "f"
        assert t.func.arg.name == "a"

    def test_type_default_level(self):
        t = pterm("Type")
        assert isinstance(t, N.U) and t.level == 0

    def test_type_explicit_level(self):
        t = pterm("Type 3")
        assert isinstance(t, N.U) and t.level == 3

    def test_prop(self):
        assert isinstance(pterm("Prop"), N.Prop)

    def test_parentheses_grouping(self):
        # f (g a)  != f g a
        grouped = pterm("f (g a)")
        assert isinstance(grouped, N.App)
        assert isinstance(grouped.arg, N.App)  # the (g a) subterm
        assert grouped.func.name == "f"
        assert grouped.arg.func.name == "g"

        flat = pterm("f g a")
        # flat applies all three left-assoc: ((f g) a), arg is a plain Const
        assert isinstance(flat.arg, N.Const)

    def test_forall_single(self):
        t = pterm("forall (x : A), e")
        assert isinstance(t, N.Pi)
        assert t.name == "x"

    def test_forall_nested(self):
        # forall (x:A) (y:B), e  ==>  Pi x. Pi y. e
        t = pterm("forall (x : A) (y : B), e")
        assert isinstance(t, N.Pi)
        assert t.name == "x"
        assert isinstance(t.codomain, N.Pi)
        assert t.codomain.name == "y"
        assert isinstance(t.codomain.codomain, N.Const)
        assert t.codomain.codomain.name == "e"

    def test_pi_multiple_binders_in_one_group(self):
        # (x y : A) -> B  ==>  Pi x. Pi y. B
        t = pterm("(x y : A) -> B")
        assert isinstance(t, N.Pi) and t.name == "x"
        assert isinstance(t.codomain, N.Pi) and t.codomain.name == "y"

    def test_bound_vs_free_in_lambda(self):
        # under `fun (A:Type)`, the inner `A` annotation refers to the bound A
        t = pterm("fun (A : Type) => fun (x : A) => x")
        assert isinstance(t, N.Lam)
        inner = t.body
        assert isinstance(inner, N.Lam)
        # the domain `A` of the inner lambda is the bound variable A
        assert isinstance(inner.domain, N.Var) and inner.domain.name == "A"


# ===========================================================================
# Round-trip: surface term -> de Bruijn -> inferred type
# ===========================================================================
class TestRoundTrip:
    def test_polymorphic_identity_infers_pi(self):
        t = pterm("fun (A : Type) => fun (x : A) => x")
        db = to_debruijn(t)
        ty = infer([], db)
        # type of  fun (A:Type) (x:A) => x  is  Pi (A:Type), A -> A
        assert isinstance(ty, KPi)
        assert isinstance(ty.domain, Univ) and ty.domain.level == 0
        # codomain is itself a (non-dependent) Pi: A -> A
        assert isinstance(ty.codomain, KPi)

    def test_arrow_type_is_a_type(self):
        # `A -> A` with A free is not closed, but `Type -> Type` is and is a sort.
        db = to_debruijn(pterm("Type -> Type"))
        ty = infer([], db)
        assert isinstance(ty, (Univ, PropSort))

    def test_prop_infers_type0(self):
        ty = infer([], to_debruijn(pterm("Prop")))
        assert isinstance(ty, Univ) and ty.level == 0


# ===========================================================================
# End-to-end execution (inline programs)
# ===========================================================================
class TestRunSourceInline:
    def test_inductive_def_and_example_qed(self, capsys):
        src = """
        inductive Nat : Type :=
          | zero : Nat
          | succ : Nat -> Nat

        def add (m : Nat) (n : Nat) : Nat :=
          Nat.rec (fun (_ : Nat) => Nat) n
                  (fun (k : Nat) (ih : Nat) => succ ih) m

        example : Nat -> Nat := fun (n : Nat) => succ n
        """
        run_source(src)
        out = capsys.readouterr().out
        assert "QED" in out
        assert "FAIL" not in out
        assert "inductive Nat" in out
        assert "def add" in out

    def test_eval_reduces(self, capsys):
        src = """
        inductive Nat : Type :=
          | zero : Nat
          | succ : Nat -> Nat
        def add (m : Nat) (n : Nat) : Nat :=
          Nat.rec (fun (_ : Nat) => Nat) n
                  (fun (k : Nat) (ih : Nat) => succ ih) m
        eval add (succ zero) (succ zero)
        """
        run_source(src)
        out = capsys.readouterr().out
        # 1 + 1 = 2  ==>  succ (succ zero)
        assert "eval" in out
        assert "(succ (succ zero))" in out
        assert "FAIL" not in out

    def test_check_prints_type(self, capsys):
        src = """
        inductive Nat : Type :=
          | zero : Nat
          | succ : Nat -> Nat
        check succ
        """
        run_source(src)
        out = capsys.readouterr().out
        assert "check" in out
        assert "(Nat -> Nat)" in out

    def test_failing_example_reports_fail(self, capsys):
        # A proof whose body does not inhabit the stated type must FAIL, not QED.
        src = """
        inductive Nat : Type :=
          | zero : Nat
          | succ : Nat -> Nat
        example : Nat -> Nat := zero
        """
        run_source(src)
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "QED" not in out

    def test_echo_false_suppresses_def_echo(self, capsys):
        src = """
        inductive Nat : Type :=
          | zero : Nat
          | succ : Nat -> Nat
        def two : Nat := succ (succ zero)
        """
        run_source(src, echo=False)
        out = capsys.readouterr().out
        # def/inductive echoes are suppressed; only check/eval/example always print
        assert "def two" not in out
        assert "inductive Nat" not in out


# ===========================================================================
# End-to-end execution of the real example files
# ===========================================================================
class TestRunRealFiles:
    def _run(self, rel):
        return run_file(os.path.join(REPO_ROOT, rel))

    def test_arith_elk(self, capsys):
        self._run(os.path.join("stdlib", "arith.elk"))
        out = capsys.readouterr().out
        assert "FAIL" not in out
        assert "QED" in out
        # 2 + 3 = 5  ==>  succ^5 zero
        assert "(succ (succ (succ (succ (succ zero)))))" in out

    def test_bool_elk(self, capsys):
        self._run(os.path.join("stdlib", "bool.elk"))
        out = capsys.readouterr().out
        assert "FAIL" not in out
        assert "eval (not true) = false" in out
        assert "eval (not false) = true" in out

    def test_logic_elk(self, capsys):
        self._run(os.path.join("stdlib", "logic.elk"))
        out = capsys.readouterr().out
        assert "FAIL" not in out
        # both examples in logic.elk are proofs that must check
        assert out.count("QED") == 2

    def test_curry_howard_elk(self, capsys):
        self._run(os.path.join("examples", "proofs", "curry_howard.elk"))
        out = capsys.readouterr().out
        assert "FAIL" not in out
        assert out.count("QED") == 2
        assert "check id" in out
        assert "check compose" in out


# ===========================================================================
# Error handling
# ===========================================================================
class TestErrors:
    def test_def_missing_type_and_body(self):
        with pytest.raises(ParseError):
            Parser(tokenize("def foo :")).parse_program()

    def test_unterminated_paren_in_term(self):
        with pytest.raises(ParseError):
            Parser(tokenize("(x : A")).parse_term([])

    def test_unterminated_paren_program(self):
        with pytest.raises(ParseError):
            Parser(tokenize("(")).parse_program()

    def test_fun_without_binder(self):
        with pytest.raises(ParseError):
            Parser(tokenize("fun => x")).parse_program()

    def test_unknown_command_keyword(self):
        with pytest.raises(ParseError):
            Parser(tokenize("wibble foo")).parse_program()

    def test_def_missing_body_after_assign(self):
        with pytest.raises(ParseError):
            Parser(tokenize("def foo : A :=")).parse_program()

    def test_run_source_propagates_parse_error(self):
        with pytest.raises(ParseError):
            run_source("def foo :", echo=False)
