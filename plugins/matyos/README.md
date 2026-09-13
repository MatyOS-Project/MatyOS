# MatyOS plugin for Claude Code

Gives Claude a trusted verification & discovery substrate — the discipline of the
scientific method, backed by a real kernel instead of a guess.

## Tools it adds

- **verify_relation** — is a number a closed form? PSLQ integer-relation search
  against pi, e, sqrt2/3/5, ln2 and the golden ratio, with a significance gate
  that rejects numerology.
- **oeis_lookup** — is an integer sequence already known? Live OEIS query.
- **check_proof** — run the trusted kernel on a `.elk` file or a project /
  `.matyos` archive; returns each theorem's certified / conditional label.
- **discover** — one pass of the discovery loop over integer-sequence seeds.

It deliberately does **not** offer "prove an arbitrary theorem" — the kernel is
sound but its library is small, so that would over-promise.

## Install

**Prerequisite:** [`uv`](https://docs.astral.sh/uv/) must be on your `PATH`
(provides `uvx`). Install once:

```bash
pip install --user uv        # or: brew install uv
```

Then, in Claude Code:

```
/plugin marketplace add MatyOS-Project/MatyOS
/plugin install matyos@matyos-plugins
/mcp                          # confirm the "matyos" server is listed
```

The plugin launches the server with `uvx --from "matyos[mcp]" matyos-mcp`, which
fetches [`matyos`](https://pypi.org/project/matyos/) from PyPI on first run — no
manual `pip install` needed.

## Honest scope

Most discovery finds are conjectures, not proofs — read the labels. The model
supplies the intelligence; MatyOS supplies the rigor.
