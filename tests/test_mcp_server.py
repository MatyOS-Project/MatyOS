"""Tests for the MatyOS MCP server tool functions.

Skipped entirely when the optional `mcp` extra is not installed. The tool
callables are plain functions (the decorator registers and returns them), so we
can exercise them directly without a live MCP session.
"""

import pytest

mcp = pytest.importorskip("mcp", reason="mcp extra not installed")
anomaly = pytest.importorskip("matyos.discovery.anomaly")

from matyos import mcp_server as srv  # noqa: E402


def test_tools_registered():
    import asyncio
    tools = asyncio.run(srv.server.list_tools())
    names = {t.name for t in tools}
    assert {"verify_relation", "oeis_lookup", "check_proof", "discover", "explore"} <= names


@pytest.mark.skipif(not anomaly.HAVE_PSLQ, reason="PSLQ needs mpmath")
def test_explore_runs_multiple_rounds():
    out = srv.explore([[0, 1, 1, 2, 3, 5, 8, 13, 21, 34]], rounds=2)
    assert out["rounds_run"] >= 1
    assert out["unique"] >= 1
    assert isinstance(out["candidates"], list)


@pytest.mark.skipif(not anomaly.HAVE_PSLQ, reason="PSLQ needs mpmath")
def test_verify_relation_finds_golden_ratio():
    # The rich number-theory basis needs real precision to be trustworthy;
    # a high-precision value (as the engine or a serious user supplies) is found.
    phi = "1.6180339887498948482045868343656381177203091798058"
    out = srv.verify_relation(phi)
    assert out["found"] is True
    assert "sqrt5" in out["closed_form"]


def test_verify_relation_reports_miss_cleanly():
    out = srv.verify_relation("0.123456789")
    assert out["found"] is False  # no small relation; must not raise


def test_oeis_lookup_known_sequence():
    out = srv.oeis_lookup([0, 1, 1, 2, 3, 5, 8, 13])
    assert out["known"] is True
    assert "A000045" in out["identifier"]


@pytest.mark.skipif(not anomaly.HAVE_PSLQ, reason="PSLQ needs mpmath")
def test_discover_returns_candidates():
    out = srv.discover([[0, 1, 1, 2, 3, 5, 8, 13, 21, 34]])
    assert out["candidates"]
    assert "sqrt5" in out["candidates"][0]["closed_form"]
