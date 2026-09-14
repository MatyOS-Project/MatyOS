"""MatyOS as an MCP server — the discipline any model can call.

Exposes MatyOS's honest, checkable operations as MCP tools so any MCP client
(Claude Code, and other hosts) can use MatyOS as a verifier and discovery
substrate: check a number for a closed form, ask whether a sequence is already
known, check a MatyOS proof, or run one pass of the discovery loop.

It deliberately does NOT offer a "prove an arbitrary theorem" tool: the kernel is
sound but its library is small, so that would over-promise. Everything here is
something MatyOS can actually stand behind.

Run:  matyos-mcp   (stdio transport)
Needs the `mcp` extra:  pip install "matyos[mcp]"  (Python 3.10+).
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from mcp.server.mcpserver import MCPServer

server = MCPServer("matyos")


@server.tool()
def verify_relation(value: str, dps: int = 50) -> dict[str, Any]:
    """Check whether a real number has a closed form (PSLQ integer relation).

    Use this to test if a numeric value (a limit, a ratio, a constant you
    computed) is secretly a simple combination of known constants such as pi, e,
    sqrt2, sqrt3, sqrt5, ln2 or the golden ratio — the Ramanujan-Machine move.

    value: the number, as a decimal string (e.g. "1.6180339887498949") or an
           exact fraction "num/den" (preferred — more precision, better result).
    dps:   working precision in decimal digits.

    Returns {"found": true, "closed_form": "x = (1 + sqrt5) / 2", ...} on a hit,
    or {"found": false} when no small relation survives the significance check.
    """
    from matyos.discovery import anomaly
    if not anomaly.HAVE_PSLQ:
        return {"found": False, "error": "mpmath not installed; PSLQ unavailable"}
    v: Any
    if "/" in value:
        v = Fraction(value)                      # exact — use full requested precision
    else:
        v = value                                # decimal string: cap precision to the
        digits = sum(c.isdigit() for c in value)  # digits actually supplied, so the
        dps = max(15, min(dps, digits))           # significance gate isn't starved
    rel = anomaly.find_closed_form(v, dps=dps)
    if rel is None:
        return {"found": False,
                "hint": "no small relation at this precision; give more digits or an exact fraction"}
    return {"found": True, "closed_form": rel.formula,
            "coeffs": list(rel.coeffs), "names": list(rel.names)}


@server.tool()
def oeis_lookup(terms: list[int]) -> dict[str, Any]:
    """Check whether an integer sequence is already known, via OEIS.

    Give at least the first ~6-8 terms. Returns whether OEIS knows it, the
    A-number and name if so, and whether the answer came from a live query or the
    offline fallback table. Use it to tell a genuinely new sequence from a
    well-known one before claiming novelty.
    """
    from matyos.discovery import verify
    ident, live = verify.oeis_lookup(tuple(terms))
    return {"known": ident is not None, "identifier": ident, "live": live}


@server.tool()
def check_proof(path: str) -> dict[str, Any]:
    """Check a MatyOS proof file (.elk) or project (directory / .matyos archive).

    Runs the trusted kernel and returns a structured result: for a project, the
    manifest with each theorem's status and its realistic label (certified /
    conditional); for a single file, the failure count and events. Use it to get
    a machine-checked verdict rather than trusting a proof by eye.
    """
    import os
    from matyos.kernel.core import reset_environment
    reset_environment()
    if os.path.isdir(path) or path.endswith(".matyos"):
        from matyos.project.engine import analyze_project
        _, failures, manifest = analyze_project(path)
        manifest["failures"] = failures
        return manifest
    from matyos.frontend.surface import Checker, ParseError
    from matyos.kernel.core import TypeError_
    checker = Checker()
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            checker.run_text(f.read(), echo=False)
        return {"kind": "file", "path": path, "failures": checker.failures,
                "events": checker.events}
    except (ParseError, TypeError_, FileNotFoundError) as e:
        return {"kind": "file", "path": path, "failures": 1,
                "error": str(e), "events": checker.events}


@server.tool()
def discover(seeds: list[list[int]], min_score: float = 0.2) -> dict[str, Any]:
    """Run one pass of the MatyOS discovery loop over integer-sequence seeds.

    Each seed is a list of integers. The engine transfers, scores (PSLQ closed
    form + cross-domain resonance), and verifies (high-precision confirm + OEIS)
    each candidate, returning a ranked shortlist with an honesty note per item.
    Most finds are conjectures, not proofs — read the labels.
    """
    from matyos.discovery.objects import Sequence
    from matyos.discovery.engine import DiscoveryEngine
    engine = DiscoveryEngine(min_score=min_score)
    objs = [Sequence.of(s, name=f"seed{i}") for i, s in enumerate(seeds)]
    return {"candidates": engine.records(objs)}


@server.tool()
def explore(seeds: list[list[int]], rounds: int = 3) -> dict[str, Any]:
    """Run several rounds of the discovery loop over integer-sequence seeds.

    Unlike `discover` (one pass), this iterates: each round it scores the current
    seeds, remembers every find, and breeds the next seeds — returning the whole
    accumulated, ranked shortlist. Breeding is deterministic (mutation), NOT an
    LLM. To have a model drive the search, call this (or `discover`) repeatedly,
    choosing the next `seeds` yourself from what came back — that is how Claude
    drives: reason over the results, then explore the directions you pick.

    seeds: list of integer-sequence seeds (each a list of ints).
    rounds: how many loop rounds to run.
    """
    from matyos.discovery.objects import Sequence
    from matyos.discovery.engine import DiscoveryEngine
    objs = [Sequence.of(s, name=f"seed{i}") for i, s in enumerate(seeds)]
    summary = DiscoveryEngine(min_score=0.2).loop(objs, rounds=rounds)
    summary["candidates"] = summary["candidates"][:15]   # keep the response bounded
    return summary


@server.tool()
def graph_conjectures() -> dict[str, Any]:
    """Conjecture inequalities between graph invariants (the Graffiti move).

    Computes cheap invariants (order, size, degrees, triangles, diameter, radius)
    over a spread of small connected graphs and returns the tight inequalities
    A(G) <= B(G) that held on every one. Each is passed through the novelty filter
    and tagged ``novelty``: "known" (an established theorem), "derived" (implied by
    known bounds — the reason gives the chain), or "candidate" (not implied by
    MatyOS's known-inequality DB — verify against the literature before treating as
    new). Candidates are listed first. They hold on the sample; proving them for
    all graphs is a human/Lean job. MatyOS never claims novelty on its own.
    """
    from matyos.discovery import graph as g
    return {"conjectures": g.classified_search()}


@server.tool()
def prove(statement: str, timeout: int = 120) -> dict[str, Any]:
    """Try to prove a Lean 4 theorem statement with mathlib automation.

    Give a Lean statement whose body is `by sorry` (the shape MatyOS's discovery
    handoff emits). MatyOS swaps the `sorry` for each tactic in a ladder (decide,
    norm_num, nlinarith, polyrith, simp, aesop), runs Lean against mathlib, and
    returns the first that compiles clean. Honest, never a fabricated proof:

    {"status": "proved", "tactic": "norm_num"} on success; "open" if no tactic
    closed it; "lean_unavailable" / "mathlib_unavailable" if the toolchain or a
    mathlib project (env MATYOS_LEAN_PROJECT) is not set up. Closes easy goals
    only — a hard or general conjecture returns "open" for a human.
    """
    from matyos.discovery import lean
    return lean.try_prove(statement, timeout=timeout)


def run() -> None:
    """Console entry point (stdio transport)."""
    server.run()  # stdio transport by default


if __name__ == "__main__":
    run()
