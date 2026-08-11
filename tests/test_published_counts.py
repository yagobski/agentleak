"""Every number published about this software must come from the software.

The marketing site advertised "all 7 compliance frameworks" while the engine
evaluated 14 — a claim written once, by hand, and then left behind as the code
moved. Understating is the harmless direction; the same mechanism overstates
just as easily, and on a product whose whole pitch is "we measure rather than
assert", an unverifiable claim is the expensive kind of wrong.

So `/api/meta` publishes the counts straight from the engine. A reviewer, an
agent, or a reader can check any figure on the site against the running software
in one request, and these tests keep that endpoint honest.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from agentleak import __version__
from agentleak.core.compliance import FRAMEWORKS
from agentleak.core.trace import CHANNELS
from agentleak.scenarios import SCENARIOS
from agentleak.scenarios.packs import list_packs
from agentleak.web.app import create_app

meta = TestClient(create_app()).get("/api/meta").json()


def test_the_frameworks_reported_are_the_frameworks_evaluated() -> None:
    assert meta["compliance_frameworks"] == [f.id for f in FRAMEWORKS]
    assert len(meta["compliance_frameworks"]) == 14


def test_the_channel_list_is_the_one_the_analyzer_walks() -> None:
    assert meta["channels"] == list(CHANNELS)
    assert len(meta["channels"]) == 8, "the docs say eight channels"


def test_the_scenario_total_is_the_sum_of_what_ships() -> None:
    scenarios = meta["scenarios"]
    assert scenarios["builtin"] == len(SCENARIOS)
    assert scenarios["packs"] == {p["id"]: p["count"] for p in list_packs()}
    assert scenarios["total"] == scenarios["builtin"] + sum(scenarios["packs"].values())
    assert scenarios["total"] == 283, "the site and the paper both quote 283"


def test_the_version_is_reported_too() -> None:
    """So a reader can tell which build produced the numbers above."""
    assert meta["version"] == __version__
