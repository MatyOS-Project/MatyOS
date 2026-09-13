# MatyOS as an MCP server

MatyOS can run as a [Model Context Protocol](https://modelcontextprotocol.io)
server, so any MCP client — Claude Code among them — can call MatyOS as a
verifier and discovery substrate. The model brings the ideas; MatyOS checks them
and labels how sure we are.

## Install

```bash
pip install "matyos[mcp]"      # pulls mcp (>=2) and mpmath; needs Python 3.10+
```

This adds a `matyos-mcp` console script that speaks MCP over stdio.

## Tools exposed

| Tool | What it does |
|---|---|
| `verify_relation` | Is a number a closed form? PSLQ integer-relation search against pi, e, sqrt2/3/5, ln2, the golden ratio. Pass a decimal string or an exact `num/den`. |
| `oeis_lookup` | Is an integer sequence already known? Live OEIS query, offline fallback. |
| `check_proof` | Run the trusted kernel on a `.elk` file or a project / `.matyos` archive; returns each theorem's status and its certified/conditional label. |
| `discover` | One pass of the discovery loop over integer-sequence seeds; returns a ranked shortlist with an honesty note per find. |
| `explore` | Several rounds of the loop (remembers + breeds) in one call. Breeding is deterministic; to have a model drive, call it (or `discover`) repeatedly, choosing the next seeds from what came back. |

Deliberately **not** exposed: a "prove an arbitrary theorem" tool. The kernel is
sound but its library is small, so that would over-promise. Everything here is
something MatyOS can actually stand behind.

## Register with Claude Code

```bash
claude mcp add matyos -- matyos-mcp
```

Or add it by hand to a `.mcp.json` the client reads:

```json
{
  "mcpServers": {
    "matyos": { "command": "matyos-mcp" }
  }
}
```

Other MCP hosts point at the same `matyos-mcp` stdio command in their own config.

## Honest scope

The model supplies the intelligence; MatyOS supplies the rigor — observe,
detect, test, refute, and a trusted judge that will not call a guess a fact.
Most discovery finds are conjectures, not proofs; read the labels.
