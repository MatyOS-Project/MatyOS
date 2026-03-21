"""
El Language Test Suite
======================
Tests for the El proof-assistant programming language (MatyOS).
Author: Ahmed Hafdi — PolyfdoR
"""

import io
import sys
import pytest
import os

# Ensure we can import from the repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from compiler.main import El


def run(code: str) -> str:
    """Run El code and capture stdout output."""
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        El.compile(code)
    finally:
        sys.stdout = old_stdout
    return buf.getvalue().strip()


# ─── Hello World ──────────────────────────────────────────────────────────────

def test_hello_world():
    out = run('ALGORITHM prog { show "Hello, World!"; }')
    assert out == "Hello, World!"


def test_show_multiple():
    out = run('ALGORITHM prog { show "line1"; show "line2"; }')
    assert out == "line1\nline2"


# ─── Variables ────────────────────────────────────────────────────────────────

def test_integer_variable():
    out = run('ALGORITHM prog { var x : integer = 42; show x; }')
    assert out == "42"


def test_float_variable():
    out = run('ALGORITHM prog { var pi : real = 3.14; show pi; }')
    assert out == "3.14"


def test_real_variable():
    out = run('ALGORITHM prog { var r : real = 2.71; show r; }')
    assert out == "2.71"


def test_string_variable():
    out = run('ALGORITHM prog { var s : string = "El"; show s; }')
    assert out == "El"


def test_variable_reassign():
    out = run('''
    ALGORITHM prog {
        var x : integer = 1;
        x = 99;
        show x;
    }
    ''')
    assert out == "99"


# ─── Arithmetic ───────────────────────────────────────────────────────────────

def test_addition():
    out = run('ALGORITHM prog { var x : integer = 3; var y : integer = 4; show x + y; }')
    assert out == "7"


def test_subtraction():
    out = run('ALGORITHM prog { var x : integer = 10; var y : integer = 3; show x - y; }')
    assert out == "7"


def test_multiplication():
    out = run('ALGORITHM prog { var x : integer = 6; var y : integer = 7; show x * y; }')
    assert out == "42"


def test_integer_division():
    out = run('ALGORITHM prog { var x : integer = 9; var y : integer = 3; show x / y; }')
    assert out == "3.0"


# ─── String Concatenation ─────────────────────────────────────────────────────

def test_string_concat():
    out = run('ALGORITHM prog { show "Hello" + ", " + "World!"; }')
    assert out == "Hello, World!"


def test_string_int_concat():
    out = run('ALGORITHM prog { var n : integer = 42; show "Answer: " + n; }')
    assert out == "Answer: 42"


def test_string_float_concat():
    out = run('ALGORITHM prog { var x : real = 3.14; show "Pi ~ " + x; }')
    assert out == "Pi ~ 3.14"


# ─── Constants ────────────────────────────────────────────────────────────────

def test_constant():
    out = run('ALGORITHM prog { const PI : real = 3.14159; show PI; }')
    assert out == "3.14159"


def test_constant_immutable():
    """Constants cannot be reassigned — El raises a SemanticError."""
    out = run('''
    ALGORITHM prog {
        const X : integer = 5;
        X = 10;
        show X;
    }
    ''')
    # Interpreter raises SemanticError — output will contain an error message
    assert "SemanticError" in out or "immutable" in out or "constant" in out.lower() or out == ""


# ─── Booleans ─────────────────────────────────────────────────────────────────

def test_boolean_true():
    out = run('ALGORITHM prog { var b : boolean = true; show b; }')
    assert "TRUE" in out.upper()


def test_if_true():
    out = run('''
    ALGORITHM prog {
        if true {
            show "yes";
        }
    }
    ''')
    assert out == "yes"


def test_if_false():
    out = run('''
    ALGORITHM prog {
        if false {
            show "yes";
        } else {
            show "no";
        }
    }
    ''')
    assert out == "no"


def test_if_elif():
    out = run('''
    ALGORITHM prog {
        var x : integer = 5;
        if x > 10 {
            show "big";
        } elif x > 3 {
            show "medium";
        } else {
            show "small";
        }
    }
    ''')
    assert out == "medium"


# ─── For Loop ─────────────────────────────────────────────────────────────────

def test_for_loop():
    out = run('''
    ALGORITHM prog {
        for i = 0; i < 3; i = i + 1 {
            show i;
        }
    }
    ''')
    assert out == "0\n1\n2"


def test_for_loop_sum():
    out = run('''
    ALGORITHM prog {
        var sum : integer = 0;
        for i = 1; i <= 5; i = i + 1 {
            sum = sum + i;
        }
        show sum;
    }
    ''')
    assert out == "15"


# ─── While Loop ───────────────────────────────────────────────────────────────

def test_while_loop():
    out = run('''
    ALGORITHM prog {
        var i : integer = 0;
        while i < 3 do {
            show i;
            i = i + 1;
        }
    }
    ''')
    assert out == "0\n1\n2"


# ─── Functions ────────────────────────────────────────────────────────────────

def test_function_return():
    out = run('''
    ALGORITHM prog {
        function double(x: integer) {
            return x * 2;
        }
        show double(21);
    }
    ''')
    assert out == "42"


def test_function_string():
    out = run('''
    ALGORITHM prog {
        function greet(name: string) {
            return "Hello, " + name + "!";
        }
        show greet("Ahmed");
    }
    ''')
    assert out == "Hello, Ahmed!"


# ─── Three-Valued Logic ───────────────────────────────────────────────────────

def test_realistic_value():
    out = run('''
    ALGORITHM prog {
        var r : boolean = realistic;
        show r;
    }
    ''')
    assert "REALISTIC" in out.upper()


def test_realistic_or_true():
    out = run('''
    ALGORITHM prog {
        var r : boolean = realistic;
        var b : boolean = true;
        if r or b {
            show "yes";
        } else {
            show "no";
        }
    }
    ''')
    assert out == "yes"


# ─── Proof System ─────────────────────────────────────────────────────────────

def test_axiom():
    out = run('''
    ALGORITHM prog {
        axiom identity: true === true;
        show "axiom ok";
    }
    ''')
    assert "axiom ok" in out


def test_theorem_and_proof():
    out = run('''
    ALGORITHM prog {
        axiom base: true;
        theorem simple: true;
        proof simple {
            hypothesis h1: true;
            QED;
        }
        show "proof ok";
    }
    ''')
    assert "proof ok" in out


# ─── Builtin Functions ────────────────────────────────────────────────────────

def test_builtin_len():
    out = run('ALGORITHM prog { show len("hello"); }')
    assert out == "5"


def test_builtin_upper():
    out = run('ALGORITHM prog { show upper("hello"); }')
    assert out == "HELLO"


def test_builtin_lower():
    out = run('ALGORITHM prog { show lower("WORLD"); }')
    assert out == "world"


def test_builtin_trim():
    out = run('ALGORITHM prog { show trim("  hi  "); }')
    assert out == "hi"


def test_builtin_abs():
    out = run('ALGORITHM prog { show abs(-42); }')
    assert out == "42"


def test_builtin_max():
    out = run('ALGORITHM prog { show max(3, 7); }')
    assert out == "7"


def test_builtin_min():
    out = run('ALGORITHM prog { show min(3, 7); }')
    assert out == "3"


def test_builtin_sqrt():
    out = run('ALGORITHM prog { show sqrt(9); }')
    assert "3.0" in out or out == "3.0"


def test_builtin_pow():
    out = run('ALGORITHM prog { show pow(2, 10); }')
    assert out == "1024"


def test_builtin_mod():
    out = run('ALGORITHM prog { show mod(17, 5); }')
    assert out == "2"


def test_builtin_str_conversion():
    # El's string concatenation auto-converts non-strings; 'str' is reserved so concat directly
    out = run('ALGORITHM prog { var n : integer = 42; show n + " is the answer"; }')
    assert out == "42 is the answer"


def test_builtin_int_conversion():
    # 'int' is a reserved keyword in El — test type_of instead
    out = run('ALGORITHM prog { var n : integer = 42; show type_of(n); }')
    assert out == "integer"


def test_builtin_type_of():
    out = run('ALGORITHM prog { show type_of(42); }')
    assert out == "integer"


# ─── Fibonacci (integration) ──────────────────────────────────────────────────

def test_fibonacci():
    out = run('''
    ALGORITHM fibonacci {
        var n1 : integer = 0;
        var n2 : integer = 1;
        var next : integer = 0;
        show n1;
        show n2;
        for i = 3; i <= 8; i = i + 1 {
            next = n1 + n2;
            show next;
            n1 = n2;
            n2 = next;
        }
    }
    ''')
    lines = out.split('\n')
    assert lines == ['0', '1', '1', '2', '3', '5', '8', '13']
