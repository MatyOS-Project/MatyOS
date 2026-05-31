"""
Project-engine test suite (MatyOS / El proof language).

Covers matyos.project.engine: project scaffolding, scientific-method file
discovery ordering, project checking over a directory and over a packed
`.matyos` archive, pack/unpack round-tripping, and the conditional-proof
dependency tracking that the engine surfaces in its report.

These tests also exercise matyos.frontend.surface.Checker directly for the
fine-grained semantics that the engine relies on (certified vs. conditional
proofs, transitivity of conjecture dependence, failing proofs, tests).

Author: Ahmed Hafdi
"""

import os
import zipfile

import pytest

from matyos.project import engine
from matyos.frontend.surface import Checker, ParseError
from matyos.kernel import core


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Both the engine and the bare Checker tests mutate the global kernel
# environment; isolate each test. (check_project also resets internally.)
@pytest.fixture(autouse=True)
def _fresh_env():
    core.reset_environment()
    yield
    core.reset_environment()


# A minimal arithmetic preamble reused by the bare-Checker semantics tests.
PRELUDE = """
inductive Nat : Type :=
  | zero : Nat
  | succ : Nat -> Nat
def add (m : Nat) (n : Nat) : Nat :=
  Nat.rec (fun (_ : Nat) => Nat) n (fun (k : Nat) (ih : Nat) => succ ih) m
def cong (A : Type) (B : Type) (f : A -> B) (a : A) (b : A) (e : Eq A a b)
    : Eq B (f a) (f b) :=
  Eq.J A a (fun (x : A) (_ : Eq A a x) => Eq B (f a) (f x)) (refl B (f a)) b e
"""


# ===========================================================================
# scaffold()
# ===========================================================================
class TestScaffold:
    def test_creates_expected_files(self, tmp_path):
        proj = os.path.join(str(tmp_path), "demo")
        engine.scaffold(proj)

        expected = [
            "theories/arithmetic/defs.elk",
            "theories/arithmetic/conjectures.hyp",
            "theories/arithmetic/nat.thm",
            "theories/arithmetic/nat.test",
            "theories/arithmetic/nat.prf",
            "matyos.toml",
        ]
        for rel in expected:
            assert os.path.isfile(os.path.join(proj, rel)), rel

    def test_manifest_interpolates_name(self, tmp_path):
        # scaffold() substitutes the `name` argument verbatim into the
        # manifest's {name} placeholder, so pass a bare project name and
        # create it relative to tmp_path (cwd-independent via chdir).
        monkey_cwd = str(tmp_path)
        old = os.getcwd()
        os.chdir(monkey_cwd)
        try:
            engine.scaffold("widgets")
            with open(os.path.join(monkey_cwd, "widgets", "matyos.toml"),
                      encoding="utf-8") as f:
                manifest = f.read()
        finally:
            os.chdir(old)
        assert 'name = "widgets"' in manifest

    def test_refuses_existing_dir(self, tmp_path):
        proj = os.path.join(str(tmp_path), "dup")
        engine.scaffold(proj)
        with pytest.raises(FileExistsError):
            engine.scaffold(proj)


# ===========================================================================
# _discover() — scientific-method ordering
# ===========================================================================
class TestDiscover:
    def test_returns_all_scaffold_files(self, tmp_path):
        proj = os.path.join(str(tmp_path), "demo")
        engine.scaffold(proj)
        found = engine._discover(proj)
        rels = {rel for _theory, rel, _kind, _abs in found}
        assert rels == {
            "theories/arithmetic/defs.elk",
            "theories/arithmetic/conjectures.hyp",
            "theories/arithmetic/nat.thm",
            "theories/arithmetic/nat.test",
            "theories/arithmetic/nat.prf",
        }
        # matyos.toml is not a known theory file -> excluded.
        assert all(not rel.endswith(".toml") for _t, rel, _k, _a in found)

    def test_scientific_method_order(self, tmp_path):
        proj = os.path.join(str(tmp_path), "demo")
        engine.scaffold(proj)
        kinds = [kind for _theory, _rel, kind, _abs in engine._discover(proj)]
        # elk before hyp before thm before test before prf
        assert kinds == ["elk", "hyp", "thm", "test", "prf"]

    def test_abspaths_exist_and_are_absolute(self, tmp_path):
        proj = os.path.join(str(tmp_path), "demo")
        engine.scaffold(proj)
        for _theory, _rel, _kind, abspath in engine._discover(proj):
            assert os.path.isabs(abspath)
            assert os.path.isfile(abspath)

    def test_order_independent_of_walk_order(self, tmp_path):
        """Files created out of phase order must still come back in phase
        order (the sort key is PHASE, then theory, then path)."""
        root = os.path.join(str(tmp_path), "scrambled")
        os.makedirs(os.path.join(root, "t"))
        # write a proof first, an .elk last
        contents = {
            "t/z.prf": "-- prf\n",
            "t/m.test": "-- test\n",
            "t/a.elk": "-- elk\n",
            "t/k.thm": "-- thm\n",
            "t/h.hyp": "-- hyp\n",
        }
        for rel, body in contents.items():
            with open(os.path.join(root, rel), "w", encoding="utf-8") as f:
                f.write(body)
        kinds = [kind for _t, _r, kind, _a in engine._discover(root)]
        assert kinds == ["elk", "hyp", "thm", "test", "prf"]


# ===========================================================================
# check_project() — directory
# ===========================================================================
class TestCheckProjectDir:
    def test_scaffold_passes(self, tmp_path):
        proj = os.path.join(str(tmp_path), "demo")
        engine.scaffold(proj)
        report, failures = engine.check_project(proj)
        assert failures == 0
        assert isinstance(report, str)

    def test_report_mentions_key_facts(self, tmp_path):
        proj = os.path.join(str(tmp_path), "demo")
        engine.scaffold(proj)
        report, _failures = engine.check_project(proj)
        for needle in ("PROVEN", "certified", "add_comm", "conjectures", "COMPLETE"):
            assert needle in report, f"missing {needle!r} in report:\n{report}"

    def test_report_summarises_counts(self, tmp_path):
        proj = os.path.join(str(tmp_path), "demo")
        engine.scaffold(proj)
        report, _failures = engine.check_project(proj)
        # 1 proven (certified), 0 open, 1 conjecture, 2 passing tests
        assert "1 proven (1 certified, 0 conditional), 0 open" in report
        assert "conjectures: 1 (realistic)" in report
        assert "2 passed, 0 failed, 0 ran" in report


# ===========================================================================
# pack() / unpack() / check_project() over a .matyos archive
# ===========================================================================
class TestArchive:
    def test_pack_produces_zip(self, tmp_path):
        proj = os.path.join(str(tmp_path), "demo")
        engine.scaffold(proj)
        out = os.path.join(str(tmp_path), "demo.matyos")
        result = engine.pack(proj, out=out)
        assert result == out
        assert os.path.isfile(out)
        assert zipfile.is_zipfile(out)

    def test_check_archive_matches_directory(self, tmp_path):
        proj = os.path.join(str(tmp_path), "demo")
        engine.scaffold(proj)
        dir_report, dir_failures = engine.check_project(proj)

        out = os.path.join(str(tmp_path), "demo.matyos")
        engine.pack(proj, out=out)
        arch_report, arch_failures = engine.check_project(out)

        assert arch_failures == 0
        assert dir_failures == 0
        # Same content surfaced; only the leading "project: <name>" differs.
        for needle in ("PROVEN", "certified", "add_comm", "conjectures", "COMPLETE"):
            assert needle in arch_report
        assert "1 proven (1 certified, 0 conditional), 0 open" in arch_report
        # The body (everything past the title banner) should be identical.
        assert dir_report.splitlines()[3:] == arch_report.splitlines()[3:]

    def test_unpack_round_trips(self, tmp_path):
        proj = os.path.join(str(tmp_path), "demo")
        engine.scaffold(proj)
        out = os.path.join(str(tmp_path), "demo.matyos")
        engine.pack(proj, out=out)

        dest = os.path.join(str(tmp_path), "restored")
        returned = engine.unpack(out, dest=dest)
        assert returned == dest

        original = {
            rel for _t, rel, _k, _a in engine._discover(proj)
        }
        restored = {
            rel for _t, rel, _k, _a in engine._discover(dest)
        }
        assert restored == original

        # And the unpacked tree still checks clean.
        report, failures = engine.check_project(dest)
        assert failures == 0
        assert "COMPLETE" in report


# ===========================================================================
# A deliberately wrong project must fail and say so.
# ===========================================================================
class TestWrongProject:
    def _make_broken(self, tmp_path):
        """Scaffold, then bolt on a theorem with a type-incorrect proof."""
        proj = os.path.join(str(tmp_path), "broken")
        engine.scaffold(proj)
        theory = os.path.join(proj, "theories", "arithmetic")
        with open(os.path.join(theory, "wrong.thm"), "w", encoding="utf-8") as f:
            f.write("theorem wrong_claim : Eq Nat zero (succ zero)\n")
        with open(os.path.join(theory, "wrong.prf"), "w", encoding="utf-8") as f:
            # refl proves `Eq Nat zero zero`, NOT `Eq Nat zero (succ zero)`.
            f.write("proof wrong_claim := refl Nat zero\n")
        return proj

    def test_wrong_proof_fails(self, tmp_path):
        proj = self._make_broken(tmp_path)
        report, failures = engine.check_project(proj)
        assert failures > 0
        assert "FAILURES" in report
        assert "exit 1" in report
        # The broken theorem is reported OPEN (its proof never certified it).
        assert "wrong_claim" in report
        # The good theorem from the scaffold still proved.
        assert "add_zero_right" in report

    def test_unknown_theorem_proof_fails(self, tmp_path):
        proj = os.path.join(str(tmp_path), "ghost")
        engine.scaffold(proj)
        theory = os.path.join(proj, "theories", "arithmetic")
        with open(os.path.join(theory, "ghost.prf"), "w", encoding="utf-8") as f:
            f.write("proof no_such_theorem := refl Nat zero\n")
        _report, failures = engine.check_project(proj)
        assert failures > 0


# ===========================================================================
# Checker semantics the engine depends on (bare, no filesystem).
# ===========================================================================
class TestCheckerSemantics:
    def test_certified_proof_has_no_deps(self):
        c = Checker()
        c.run_text(PRELUDE + """
theorem add_zero_right : forall (n : Nat), Eq Nat (add n zero) n
proof add_zero_right :=
  fun (n : Nat) =>
    Nat.rec (fun (m : Nat) => Eq Nat (add m zero) m)
            (refl Nat zero)
            (fun (k : Nat) (ih : Eq Nat (add k zero) k) =>
                cong Nat Nat succ (add k zero) k ih)
            n
""", echo=False)
        assert c.failures == 0
        assert "add_zero_right" in c.proven
        assert c.cond_deps.get("add_zero_right") == set()

    def test_proof_using_conjecture_is_conditional(self):
        c = Checker()
        c.run_text(PRELUDE + """
conjecture add_comm : forall (a : Nat), forall (b : Nat), Eq Nat (add a b) (add b a)
theorem comm_restated : forall (a : Nat), forall (b : Nat), Eq Nat (add a b) (add b a)
proof comm_restated := add_comm
""", echo=False)
        assert c.failures == 0
        assert "comm_restated" in c.proven
        assert c.cond_deps.get("comm_restated") == {"add_comm"}

    def test_conditional_dependence_is_transitive(self):
        """A proof that uses a *lemma* which itself used a conjecture must
        still be flagged conditional on that conjecture."""
        c = Checker()
        c.run_text(PRELUDE + """
conjecture add_comm : forall (a : Nat), forall (b : Nat), Eq Nat (add a b) (add b a)
def lemma_uses (a : Nat) (b : Nat) : Eq Nat (add a b) (add b a) := add_comm a b
theorem via_lemma : forall (a : Nat), forall (b : Nat), Eq Nat (add a b) (add b a)
proof via_lemma := fun (a : Nat) => fun (b : Nat) => lemma_uses a b
""", echo=False)
        assert c.failures == 0
        assert "via_lemma" in c.proven
        # The conjecture is reached only via lemma_uses, never named directly.
        assert c.cond_deps.get("via_lemma") == {"add_comm"}

    def test_wrong_type_proof_fails_and_is_not_proven(self):
        c = Checker()
        c.run_text(PRELUDE + """
theorem bogus : Eq Nat zero (succ zero)
proof bogus := refl Nat zero
""", echo=False)
        assert c.failures == 1
        assert "bogus" not in c.proven

    def test_proof_for_unknown_theorem_fails(self):
        c = Checker()
        c.run_text(PRELUDE + """
proof phantom := refl Nat zero
""", echo=False)
        assert c.failures == 1
        assert "phantom" not in c.proven

    def test_test_equation_passes(self):
        c = Checker()
        c.run_text(PRELUDE + """
test add_1_1 : add (succ zero) (succ zero) = succ (succ zero)
""", echo=False)
        assert c.failures == 0
        statuses = [e["status"] for e in c.events if e["kind"] == "test"]
        assert statuses == ["passed"]

    def test_test_equation_fails(self):
        c = Checker()
        c.run_text(PRELUDE + """
test wrong : add (succ zero) (succ zero) = succ zero
""", echo=False)
        assert c.failures == 1
        statuses = [e["status"] for e in c.events if e["kind"] == "test"]
        assert statuses == ["failed"]

    def test_test_without_rhs_just_runs(self):
        c = Checker()
        c.run_text(PRELUDE + """
test normal_form : add (succ zero) (succ zero)
""", echo=False)
        assert c.failures == 0
        statuses = [e["status"] for e in c.events if e["kind"] == "test"]
        assert statuses == ["ran"]


# ---------------------------------------------------------------------------
# Sealing a completed project into a compressed .matyos archive (build/info)
# ---------------------------------------------------------------------------
class TestBuildSeal:
    def test_build_seals_completed_project(self, tmp_path):
        proj = tmp_path / "thy"
        engine.scaffold(str(proj))
        out = tmp_path / "thy.matyos"
        res = engine.build_project(str(proj), out=str(out), timestamp="T")
        assert res["completed"] is True
        assert res["out"] == str(out)
        assert out.exists()
        import zipfile
        names = zipfile.ZipFile(str(out)).namelist()
        assert "MANIFEST.json" in names and "REPORT.txt" in names

    def test_manifest_round_trips(self, tmp_path):
        proj = tmp_path / "thy"
        engine.scaffold(str(proj))
        out = tmp_path / "thy.matyos"
        engine.build_project(str(proj), out=str(out), timestamp="T")
        m = engine.read_manifest(str(out))
        assert m["completed"] is True
        assert m["summary"]["open"] == 0
        assert m["summary"]["certified"] >= 1
        assert m["summary"]["conjectures"] >= 1

    def test_incomplete_project_not_sealed(self, tmp_path):
        proj = tmp_path / "thy"
        engine.scaffold(str(proj))
        # add an unproved theorem -> open obligation -> not completed
        (proj / "theories" / "arithmetic" / "open.thm").write_text(
            "theorem unproved : forall (A : Type), A -> A\n", encoding="utf-8")
        res = engine.build_project(str(proj), out=str(tmp_path / "x.matyos"))
        assert res["completed"] is False
        assert res["out"] is None
        assert not (tmp_path / "x.matyos").exists()

    def test_force_seals_incomplete(self, tmp_path):
        proj = tmp_path / "thy"
        engine.scaffold(str(proj))
        (proj / "theories" / "arithmetic" / "open.thm").write_text(
            "theorem unproved : forall (A : Type), A -> A\n", encoding="utf-8")
        out = tmp_path / "x.matyos"
        res = engine.build_project(str(proj), out=str(out), force=True)
        assert res["out"] == str(out) and out.exists()
        assert res["manifest"]["completed"] is False
