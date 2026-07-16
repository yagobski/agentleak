"""Source-level contracts for UI behavior that is otherwise browser-only.

The frontend build type-checks React but has no DOM test runtime. These focused
contracts keep the landing preview and mobile sidebar regressions visible in CI;
the full interaction is still exercised by the browser smoke test before deploy.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1] / "agentleak" / "web" / "frontend" / "src"


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_hero_preview_exposes_five_working_views() -> None:
    landing = _source("pages/Landing.tsx")
    expected = ("Dashboard", "Runs", "Playground", "Leaderboard", "Scenarios")

    assert (
        'const HERO_VIEWS = ["Dashboard", "Runs", "Playground", '
        '"Leaderboard", "Scenarios"] as const'
    ) in landing
    for view in expected:
        assert f'view === "{view}"' in landing
    for view in ("Playground", "Leaderboard", "Scenarios"):
        assert f'onClick={{() => setView("{view}")}}' in landing


def test_hero_preview_has_layouts_for_non_dashboard_views() -> None:
    css = _source("index.css")

    for selector in (
        ".cursor-app-runs-full",
        ".cursor-app-board-row",
        ".cursor-app-playground",
        ".cursor-app-scenarios",
    ):
        assert selector in css


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
