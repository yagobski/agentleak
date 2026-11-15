# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The GUI reads the source/emission channel split from /api/meta."""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agentleak.core.agentrisk import BASELINE_CHANNELS  # noqa: E402
from agentleak.core.store import Store  # noqa: E402
from agentleak.web import create_app  # noqa: E402


def test_meta_splits_source_and_emission_channels(tmp_path):
    meta = TestClient(create_app(store=Store(str(tmp_path / "m.db")))).get("/api/meta").json()
    assert set(meta["source_channels"]) == set(BASELINE_CHANNELS)
    assert set(meta["source_channels"]).isdisjoint(meta["emission_channels"])
    assert sorted(meta["source_channels"] + meta["emission_channels"]) == sorted(meta["channels"])
    assert "final_output" in meta["emission_channels"]
