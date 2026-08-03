"""Source-level contracts for UI behavior that is otherwise browser-only.

The frontend build type-checks React but has no DOM test runtime. These focused
contracts keep product-UI regressions visible in CI; the full interaction is
still exercised by the browser smoke test before deploy. Marketing-page
contracts live in the site repository alongside the pages they describe.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1] / "agentleak" / "web" / "frontend" / "src"


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_platform_mobile_sidebar_closes_after_navigation() -> None:
    shell = _source("layout/AppShell.tsx")

    assert "const { setOpenMobile } = useSidebar()" in shell
    assert "setOpenMobile(false)" in shell
    assert "[pathname, setOpenMobile]" in shell


def test_platform_logo_header_uses_the_shared_52px_alignment() -> None:
    css = _source("index.css")

    assert '.platform-sidebar [data-sidebar="header"] { display: flex; height: 52px;' in css
    assert "justify-content: center" in css
    assert ".platform-sidebar .agentleak-logo-platform { top: -3px;" in css
