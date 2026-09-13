"""Let a model drive the search — Claude, or any other LLM.

The engine's loop needs to decide *what to try next*. By default it does that with
fixed mutations (no model). This module lets that decision come from a reasoner
instead — and the reasoner is model-agnostic: you hand it a function that calls
*your* model (Claude, GPT, a local model), and it returns the next seeds to try.
MatyOS never hardcodes a provider, so no API key or SDK is required to import it.

- `MutationReasoner` — the default; proposes seeds by mutating the current ones.
- `CallbackReasoner(fn)` — wraps any model: `fn(context)` returns either a list of
  integer-sequence seeds, or free text from which seeds are parsed.
- `prompt_for(context)` — renders the search state into a prompt you can send to a
  model, so wiring one in is a few lines.
"""

from __future__ import annotations

import re
from typing import Callable, Protocol


class Reasoner(Protocol):
    def propose(self, context: dict) -> list[list[int]]:
        """Return the next integer-sequence seeds to explore, given the state."""
        ...


class MutationReasoner:
    """Default, no model: propose the next seeds by mutating the current frontier."""

    def propose(self, context: dict) -> list[list[int]]:
        from matyos.discovery.objects import Sequence
        from matyos.discovery import generator
        out: list[list[int]] = []
        for seq in context.get("frontier", []):
            s = Sequence.of(seq)
            for m in generator.mutate(s):
                if all(t.denominator == 1 for t in m.terms):
                    out.append([int(t) for t in m.terms])
        return out


def parse_seeds(text: str) -> list[list[int]]:
    """Pull integer-sequence seeds out of a model's free-text reply.

    Accepts anything with bracketed integer lists, e.g. "try [2,4,6,8] and
    [1,1,2,3,5,8]". Lists shorter than 4 terms are ignored (too little to fit).
    """
    seeds: list[list[int]] = []
    for chunk in re.findall(r"\[[-0-9,\s]+\]", text):
        nums = re.findall(r"-?\d+", chunk)
        if len(nums) >= 4:
            seeds.append([int(x) for x in nums])
    return seeds


class CallbackReasoner:
    """Model-agnostic driver. `fn(context)` may return a list of seeds (each a
    list of ints) or a text string that seeds are parsed from. This is how Claude
    or any other LLM drives the engine — you supply the function that calls it."""

    def __init__(self, fn: Callable[[dict], object]) -> None:
        self.fn = fn

    def propose(self, context: dict) -> list[list[int]]:
        out = self.fn(context)
        if isinstance(out, str):
            return parse_seeds(out)
        return [[int(x) for x in seq] for seq in out]


def prompt_for(context: dict) -> str:
    """Render the search state as a prompt for a model to propose the next seeds."""
    lines = [
        "You are guiding a mathematical discovery engine. It finds closed forms and",
        "flags unexplained 'mystery' constants. Given what has been found so far,",
        "propose the next integer sequences to investigate — as bracketed lists,",
        "e.g. [1,2,4,8,16]. Prefer directions likely to reveal something new.",
        "",
        f"Seeds tried so far: {context.get('frontier', [])}",
    ]
    found = context.get("found", [])
    if found:
        lines.append("Closed forms found: " + "; ".join(found[:10]))
    myst = context.get("mysteries", [])
    if myst:
        lines.append("Mystery constants (no known closed form): " + "; ".join(myst[:10]))
    lines.append("\nReply with the sequences to try next.")
    return "\n".join(lines)
