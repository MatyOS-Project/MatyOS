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


def test_check_json_file(capsys):
    import json
    assert main(["check", "--json", "stdlib/arith.elk"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["kind"] == "file" and data["failures"] == 0
    assert any(e["kind"] == "example" and e["status"] == "PROVEN"
               for e in data["events"])


def test_check_json_project(capsys):
    import json
    assert main(["check", "--json", "examples/projects/arithmetic"]) == 0
    m = json.loads(capsys.readouterr().out)
    assert m["completed"] is True
    assert m["summary"]["certified"] >= 3
    assert "theories/nat" in m["theories"]


def test_realistic_verdicts(capsys):
    # three-valued logic reachable from the CLI: TRUE / FALSE / (REALISTIC) / UNKNOWN
    assert main(["realistic", "radius <= diameter"]) == 0   # a known theorem
    assert "TRUE" in capsys.readouterr().out

    assert main(["realistic", "diameter <= radius"]) == 0
    assert "FALSE" in capsys.readouterr().out

    assert main(["realistic", "foo <= bar"]) == 0
    assert "UNKNOWN" in capsys.readouterr().out


def test_realistic_json(capsys):
    import json
    assert main(["realistic", "radius <= diameter", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["truth"] == "true" and d["verdict"] == "realistic" and d["known"] is True


def test_realistic_needs_claim(capsys):
    assert main(["realistic"]) == 2
    assert "needs a claim" in capsys.readouterr().err


def test_realistic_domain_triangles(capsys):
    # Euler's inequality is judgeable from the terminal in the triangles domain
    assert main(["realistic", "--domain", "triangles",
                 "tworadius <= circumradius"]) == 0
    out = capsys.readouterr().out
    assert "REALISTIC" in out          # holds on the strong battery, unproven
    # a counterexample bound comes back FALSE
    assert main(["realistic", "--domain", "triangles", "longest <= shortest"]) == 0
    assert "FALSE" in capsys.readouterr().out


def test_realistic_unknown_domain(capsys):
    assert main(["realistic", "--domain", "nope", "a <= b"]) == 2
    assert "unknown domain" in capsys.readouterr().err
