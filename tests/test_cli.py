"""Tests for the `matyos` command-line interface (matyos.cli.main)."""

import pytest

from matyos.cli import main
from matyos.kernel import core


@pytest.fixture(autouse=True)
def _isolate():
    core.reset_environment()
    yield
    core.reset_environment()


def test_version(capsys):
    assert main(["version"]) == 0
    assert "MatyOS" in capsys.readouterr().out


def test_no_args_shows_usage(capsys):
    assert main([]) == 0
    assert "Commands:" in capsys.readouterr().out


def test_help(capsys):
    assert main(["help"]) == 0
    assert "check" in capsys.readouterr().out


def test_check_arith_qed(capsys):
    assert main(["check", "stdlib/arith.elk"]) == 0
    assert "QED" in capsys.readouterr().out


def test_bare_path_is_checked(capsys):
    assert main(["stdlib/arith.elk"]) == 0
    assert "QED" in capsys.readouterr().out


def test_missing_file_exits_2(capsys):
    assert main(["check", "does_not_exist.elk"]) == 2
    assert "not found" in capsys.readouterr().err


def test_unknown_command_exits_2(capsys):
    assert main(["frobnicate"]) == 2
    assert "unknown command" in capsys.readouterr().err


def test_check_without_file_exits_2(capsys):
    assert main(["check"]) == 2


def test_failing_proof_exits_1(tmp_path, capsys):
    # a deliberately false claim: identity does not prove A -> B
    bad = tmp_path / "bad.elk"
    bad.write_text(
        "example : forall (A : Type), forall (B : Type), A -> B := "
        "fun (A : Type) (B : Type) (x : A) => x\n",
        encoding="utf-8",
    )
    assert main(["check", str(bad)]) == 1
    out = capsys.readouterr()
    assert "FAIL" in out.out or "FAILED" in out.err
