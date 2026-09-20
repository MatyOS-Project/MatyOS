"""MatyOS hard-problems workspace — an HONEST engagement layer, NOT a solver.

See :mod:`matyos.problems.famous`. MatyOS can *state* famous open problems
formally, *verify finite* cases, *explore adjacent* sequences, and *track* known
results. It cannot prove them, and nothing here ever reports one as proved.
"""

from matyos.problems.famous import (
    FamousProblem, FiniteEvidence, REGISTRY,
    state, status, verify_finite, explore_adjacent,
)

__all__ = [
    "FamousProblem", "FiniteEvidence", "REGISTRY",
    "state", "status", "verify_finite", "explore_adjacent",
]
