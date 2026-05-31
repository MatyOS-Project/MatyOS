"""Library regression: the standard library and showcase theories must keep
type-checking — including the proof that addition is commutative."""

import os
import pytest

from matyos.kernel import core
from matyos.frontend.surface import run_file
from matyos.project.engine import check_project

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(autouse=True)
def _isolate():
    core.reset_environment()
    yield
    core.reset_environment()


@pytest.mark.parametrize("path", [
    "stdlib/arith.elk", "stdlib/bool.elk", "stdlib/logic.elk", "stdlib/eq.elk",
    "examples/proofs/curry_howard.elk", "examples/proofs/tactics.elk",
])
def test_stdlib_files_check(path):
    assert run_file(os.path.join(ROOT, path)) == 0


def test_eq_toolkit_defines_symm_trans_cong_subst():
    run_file(os.path.join(ROOT, "stdlib/eq.elk"))
    for name in ("symm", "trans", "cong", "subst"):
        assert name in core._GLOBALS


def test_arithmetic_project_proves_commutativity():
    report, failures = check_project(
        os.path.join(ROOT, "examples/projects/arithmetic"))
    assert failures == 0
    assert "add_comm" in report
    assert "[PROVEN] add_comm" in report
    # commutativity must be CERTIFIED, not merely conditional
    assert "open" in report and "0 open" in report


def test_logic_project_still_checks():
    report, failures = check_project(
        os.path.join(ROOT, "examples/projects/logic"))
    assert failures == 0
