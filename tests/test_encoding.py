"""A real-world file may carry a UTF-8 BOM (Windows editors/PowerShell add one).
The checker must tolerate it rather than choke on the leading character."""

import pytest

from matyos.frontend.surface import run_source, run_file
from matyos.kernel import core


@pytest.fixture(autouse=True)
def _isolate():
    core.reset_environment()
    yield
    core.reset_environment()


PROG = "example : forall (A : Type), A -> A := fun (A : Type) (x : A) => x\n"


def test_run_source_tolerates_bom(capsys):
    failures = run_source("﻿" + PROG)
    assert failures == 0
    assert "QED" in capsys.readouterr().out


def test_run_file_with_bom(tmp_path, capsys):
    p = tmp_path / "bom.elk"
    p.write_text(PROG, encoding="utf-8-sig")  # writes a BOM
    assert run_file(str(p)) == 0
    assert "QED" in capsys.readouterr().out
