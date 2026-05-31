"""
Tests for the scientific-method commands of the MatyOS surface language:

    theorem / proof / hypothesis / conjecture / test

These commands turn the surface language into a "scientific notebook": you state
obligations (theorems), discharge them with kernel-checked proofs, assume
realistic truths (hypotheses/conjectures), and run computational experiments
(tests). The key property under test is the *epistemic bookkeeping*: a proof is
PROVEN-certified only if it relies on no conjecture, and conditionality is
propagated transitively through lemmas.

Expectations were derived by running the system (see matyos/frontend/surface.py
Checker and matyos/project/engine.py).
"""

import os
import shutil
import tempfile

import pytest

from matyos.kernel import core
from matyos.frontend.surface import Checker, ParseError, run_source
from matyos.project import engine


# A minimal shared vocabulary: Peano Nat + addition. Used by most programs.
NAT = """
inductive Nat : Type :=
  | zero : Nat
  | succ : Nat -> Nat

def add (m : Nat) (n : Nat) : Nat :=
  Nat.rec (fun (_ : Nat) => Nat) n (fun (k : Nat) (ih : Nat) => succ ih) m
"""


@pytest.fixture(autouse=True)
def fresh_kernel():
    """Every test starts from a clean kernel environment."""
    core.reset_environment()
    yield
    core.reset_environment()


def _checker_with_nat():
    c = Checker()
    c.run_text(NAT, echo=False)
    return c


# --------------------------------------------------------------------------
# theorem + proof : certified
# --------------------------------------------------------------------------
def test_theorem_then_certified_proof():
    c = _checker_with_nat()
    c.run_text("theorem refl_zero : Eq Nat zero zero", echo=False)

    # Stating an obligation registers it as pending, not yet proven.
    assert "refl_zero" in c.obligations
    assert "refl_zero" not in c.proven

    c.run_text("proof refl_zero := refl Nat zero", echo=False)

    assert "refl_zero" in c.proven
    assert c.cond_deps["refl_zero"] == set()   # certified: no assumptions
    assert c.failures == 0


def test_certified_proof_logs_proven_event():
    c = _checker_with_nat()
    c.run_text("theorem refl_zero : Eq Nat zero zero", echo=False)
    c.run_text("proof refl_zero := refl Nat zero", echo=False)

    proof_events = [e for e in c.events if e["kind"] == "proof"]
    assert proof_events[-1]["name"] == "refl_zero"
    assert proof_events[-1]["status"] == "PROVEN"
    assert proof_events[-1]["detail"] == "certified"
    assert proof_events[-1]["deps"] == []


# --------------------------------------------------------------------------
# hypothesis / conjecture : assumed truths land in .assumptions
# --------------------------------------------------------------------------
def test_hypothesis_lands_in_assumptions():
    c = _checker_with_nat()
    c.run_text("hypothesis h1 : Eq Nat zero zero", echo=False)

    assert "h1" in c.assumptions
    # An assumption depends on itself (so anything using it is conditional).
    assert c.cond_deps["h1"] == {"h1"}
    assert c.failures == 0


def test_conjecture_lands_in_assumptions():
    c = _checker_with_nat()
    c.run_text(
        "conjecture comm : forall (a : Nat), forall (b : Nat), "
        "Eq Nat (add a b) (add b a)",
        echo=False,
    )

    assert "comm" in c.assumptions
    assert c.cond_deps["comm"] == {"comm"}
    assert c.failures == 0


def test_hypothesis_and_conjecture_events():
    c = _checker_with_nat()
    c.run_text("hypothesis h1 : Eq Nat zero zero", echo=False)
    c.run_text("conjecture cj : Eq Nat zero zero", echo=False)

    hyp = [e for e in c.events if e["kind"] == "hypothesis"][-1]
    conj = [e for e in c.events if e["kind"] == "conjecture"][-1]
    assert hyp["status"] == "assumed (realistic)"
    assert conj["status"] == "conjectured (realistic)"


# --------------------------------------------------------------------------
# proof using a conjecture : PROVEN but CONDITIONAL
# --------------------------------------------------------------------------
def test_proof_using_conjecture_is_conditional():
    c = _checker_with_nat()
    c.run_text(
        "conjecture comm : forall (a : Nat), forall (b : Nat), "
        "Eq Nat (add a b) (add b a)",
        echo=False,
    )
    c.run_text("theorem lemA : Eq Nat (add zero zero) (add zero zero)", echo=False)
    c.run_text("proof lemA := comm zero zero", echo=False)

    # It IS proven (kernel-accepted), but conditional on the open conjecture.
    assert "lemA" in c.proven
    assert c.cond_deps["lemA"] == {"comm"}
    assert c.failures == 0

    proof_events = [e for e in c.events if e["kind"] == "proof"]
    assert proof_events[-1]["status"] == "CONDITIONAL"
    assert proof_events[-1]["deps"] == ["comm"]


# --------------------------------------------------------------------------
# transitive conditionality : B proven via lemma A which used conjecture C
# --------------------------------------------------------------------------
def test_conditionality_is_transitive():
    c = _checker_with_nat()
    c.run_text(
        "conjecture comm : forall (a : Nat), forall (b : Nat), "
        "Eq Nat (add a b) (add b a)",
        echo=False,
    )
    # Lemma A is proven *via* the conjecture -> conditional on comm.
    c.run_text("theorem lemA : Eq Nat (add zero zero) (add zero zero)", echo=False)
    c.run_text("proof lemA := comm zero zero", echo=False)
    assert c.cond_deps["lemA"] == {"comm"}

    # Theorem B is proven *via* lemma A and never mentions comm directly,
    # yet must inherit the conjecture dependency transitively.
    c.run_text("theorem thmB : Eq Nat (add zero zero) (add zero zero)", echo=False)
    c.run_text("proof thmB := lemA", echo=False)

    assert "thmB" in c.proven
    assert c.cond_deps["thmB"] == {"comm"}
    assert c.failures == 0


def test_certified_lemma_does_not_pollute_dependent():
    """A proof that uses only a *certified* lemma stays certified."""
    c = _checker_with_nat()
    c.run_text("theorem lemC : Eq Nat zero zero", echo=False)
    c.run_text("proof lemC := refl Nat zero", echo=False)
    assert c.cond_deps["lemC"] == set()

    c.run_text("theorem thmD : Eq Nat zero zero", echo=False)
    c.run_text("proof thmD := lemC", echo=False)
    assert "thmD" in c.proven
    assert c.cond_deps["thmD"] == set()
    assert c.failures == 0


# --------------------------------------------------------------------------
# failing proofs : raise .failures and DO NOT enter .proven
# --------------------------------------------------------------------------
def test_wrong_typed_proof_fails():
    c = _checker_with_nat()
    # 0 = succ 0 is false; refl proves 0 = 0, the wrong type.
    c.run_text("theorem bad : Eq Nat zero (succ zero)", echo=False)
    c.run_text("proof bad := refl Nat zero", echo=False)

    assert c.failures == 1
    assert "bad" not in c.proven

    proof_events = [e for e in c.events if e["kind"] == "proof"]
    assert proof_events[-1]["status"] == "FAILED"


def test_proof_of_unknown_theorem_fails():
    c = _checker_with_nat()
    # No `theorem nope` was ever stated.
    c.run_text("proof nope := refl Nat zero", echo=False)

    assert c.failures == 1
    assert "nope" not in c.proven

    proof_events = [e for e in c.events if e["kind"] == "proof"]
    assert proof_events[-1]["status"] == "FAILED"
    assert proof_events[-1]["detail"] == "no such theorem"


def test_failed_proof_then_successful_proof():
    """A failure does not block a later, correct proof of another theorem."""
    c = _checker_with_nat()
    c.run_text("proof ghost := refl Nat zero", echo=False)  # unknown -> fail
    c.run_text("theorem ok : Eq Nat zero zero", echo=False)
    c.run_text("proof ok := refl Nat zero", echo=False)

    assert c.failures == 1
    assert "ok" in c.proven
    assert "ghost" not in c.proven


# --------------------------------------------------------------------------
# test command : passed / failed / ran
# --------------------------------------------------------------------------
def test_test_passing():
    c = _checker_with_nat()
    c.run_text("test t : add zero zero = zero", echo=False)

    assert c.failures == 0
    last = [e for e in c.events if e["kind"] == "test"][-1]
    assert last["status"] == "passed"


def test_test_failing_increments_failures():
    c = _checker_with_nat()
    c.run_text("test t : add zero (succ zero) = zero", echo=False)

    assert c.failures == 1
    last = [e for e in c.events if e["kind"] == "test"][-1]
    assert last["status"] == "failed"


def test_test_without_rhs_just_runs():
    c = _checker_with_nat()
    c.run_text("test t : add (succ zero) zero", echo=False)

    # Normalizing without comparison is informational only.
    assert c.failures == 0
    last = [e for e in c.events if e["kind"] == "test"][-1]
    assert last["status"] == "ran"


def test_multiple_tests_accumulate_failures():
    c = _checker_with_nat()
    c.run_text("test a : add zero zero = zero", echo=False)              # pass
    c.run_text("test b : add zero (succ zero) = zero", echo=False)       # fail
    c.run_text("test c : add (succ zero) (succ zero)", echo=False)       # ran
    c.run_text("test d : succ zero = zero", echo=False)                  # fail

    assert c.failures == 2
    statuses = [e["status"] for e in c.events if e["kind"] == "test"]
    assert statuses == ["passed", "failed", "ran", "failed"]


# --------------------------------------------------------------------------
# module-level entry point
# --------------------------------------------------------------------------
def test_run_source_returns_failure_count():
    program = NAT + "\ntheorem ok : Eq Nat zero zero\nproof ok := refl Nat zero\n"
    assert run_source(program, echo=False) == 0

    bad = NAT + "\nproof nope := refl Nat zero\n"
    assert run_source(bad, echo=False) == 1


def test_parse_error_is_raised_and_exported():
    assert issubclass(ParseError, Exception)
    with pytest.raises(ParseError):
        Checker().run_text("theorem", echo=False)  # missing name/body


# --------------------------------------------------------------------------
# project engine : the scientific method as a file system
# --------------------------------------------------------------------------
@pytest.fixture
def workdir():
    d = tempfile.mkdtemp(prefix="matyos_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_scaffold_and_check_project(workdir):
    proj = os.path.join(workdir, "proj")
    engine.scaffold(proj)

    report, failures = engine.check_project(proj)

    assert failures == 0
    # The scaffold proves add_zero_right (certified) and has an open conjecture.
    assert "[PROVEN] add_zero_right" in report
    assert "certified" in report
    assert "add_comm" in report
    # 2 passing tests.
    assert "2 passed" in report


def test_discover_orders_by_scientific_phase(workdir):
    proj = os.path.join(workdir, "proj")
    engine.scaffold(proj)

    kinds = [k for _, _, k, _ in engine._discover(proj)]
    # definitions -> hypotheses -> theorems -> tests -> proofs
    assert kinds == ["elk", "hyp", "thm", "test", "prf"]


def test_pack_unpack_roundtrip_checks_clean(workdir):
    proj = os.path.join(workdir, "proj")
    engine.scaffold(proj)

    archive = engine.pack(proj, out=os.path.join(workdir, "proj.matyos"))
    assert os.path.isfile(archive)

    # check_project works directly on the archive.
    _, archive_failures = engine.check_project(archive)
    assert archive_failures == 0

    dest = engine.unpack(archive, dest=os.path.join(workdir, "unpacked"))
    assert len(engine._discover(dest)) == 5
