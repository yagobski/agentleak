"""Regression tests for the first-session papercuts found in the 2026-08 audit.

Each of these was a wall a developer hit in their first minutes with the tool:
a single-file scan that errored, a local run that printed a connection error at
someone who never asked for a platform, a published benchmark that was hidden
behind a UI import, and a defenses module with no door into it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentleak.cli import app
from agentleak.core.codescan import scan_file, scan_path

runner = CliRunner()

LEAKY_SOURCE = (
    'API_KEY = "sk-live-a1b2c3d4e5f6g7h8"\n'
    'def sync(user):\n'
    '    print(f"syncing {user[\'ssn\']} to CRM")\n'
)


# -- scanning a single file -------------------------------------------------
def test_scan_file_accepts_one_file(tmp_path: Path) -> None:
    target = tmp_path / "bot.py"
    target.write_text(LEAKY_SOURCE, encoding="utf-8")

    result = scan_file(target)

    assert result.findings, "a hardcoded secret must be reported"
    assert result.source_type == "file"
    assert any(f.rule == "hardcoded_secret" for f in result.findings)


def test_scan_file_rejects_a_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Not a file"):
        scan_file(tmp_path)


def test_scan_path_dispatches_on_what_it_is(tmp_path: Path) -> None:
    target = tmp_path / "bot.py"
    target.write_text(LEAKY_SOURCE, encoding="utf-8")

    assert scan_path(target).source_type == "file"
    assert scan_path(tmp_path).source_type == "dir"
    with pytest.raises(ValueError, match="No such file or directory"):
        scan_path(tmp_path / "nope.py")


def test_scan_file_ignores_extension_filters(tmp_path: Path) -> None:
    # An explicitly named file is always scanned, even with an odd extension:
    # the user pointed at it on purpose.
    target = tmp_path / "config.weird"
    target.write_text('password = "hunter2-not-a-real-secret-value"\n', encoding="utf-8")
    assert scan_file(target).files_scanned == 1


def test_cli_scan_on_a_single_file(tmp_path: Path) -> None:
    target = tmp_path / "bot.py"
    target.write_text(LEAKY_SOURCE, encoding="utf-8")

    result = runner.invoke(app, ["scan", str(target)])

    assert result.exit_code == 0, result.output
    assert "Not a directory" not in result.output
    assert "hardcoded_secret" in result.output


# -- local-first watch(): silent unless a platform was configured -----------
def _leaky_run(**kwargs: object):
    import agentleak

    with agentleak.watch("papercut-test", print_summary=False, **kwargs) as run:  # type: ignore[arg-type]
        run.tool_call({"ssn": "123-45-6789"}, target="crm")
        run.final_output("done")
    return run


def test_watch_does_not_submit_without_a_configured_platform(monkeypatch) -> None:
    monkeypatch.delenv("AGENTLEAK_PLATFORM_URL", raising=False)

    run = _leaky_run()

    assert run.report is not None, "analysis is always local and always happens"
    assert run.submitted is None
    assert run.submit_error is None, "no failed connection the user never asked for"
    assert "platform submission failed" not in run.summary()


def test_watch_submits_when_the_env_var_configures_a_platform(monkeypatch) -> None:
    # Port 9 is the discard port: reliably refuses, so submission is attempted
    # and fails loudly, which is what an explicit opt-in should do.
    monkeypatch.setenv("AGENTLEAK_PLATFORM_URL", "http://127.0.0.1:9")

    run = _leaky_run()

    assert run.report is not None
    assert run.submit_error is not None
    assert "platform submission failed" in run.summary()


def test_watch_submits_when_base_url_is_explicit(monkeypatch) -> None:
    monkeypatch.delenv("AGENTLEAK_PLATFORM_URL", raising=False)

    run = _leaky_run(base_url="http://127.0.0.1:9")

    assert run.submit_error is not None


def test_watch_submit_false_wins_over_configuration(monkeypatch) -> None:
    monkeypatch.setenv("AGENTLEAK_PLATFORM_URL", "http://127.0.0.1:9")

    run = _leaky_run(submit=False)

    assert run.submitted is None and run.submit_error is None


# -- the published benchmark is one command away ---------------------------
def test_scenarios_lists_packs() -> None:
    result = runner.invoke(app, ["scenarios", "--packs"])

    assert result.exit_code == 0, result.output
    assert "agentleak_bench" in result.output
    assert "36 scenario(s)" in result.output


def test_scenarios_lists_one_packs_contents() -> None:
    result = runner.invoke(app, ["scenarios", "--pack", "agentleak_bench"])

    assert result.exit_code == 0, result.output
    assert "36 scenario(s) in agentleak_bench" in result.output


def test_scenarios_rejects_an_unknown_pack() -> None:
    result = runner.invoke(app, ["scenarios", "--pack", "does_not_exist"])
    assert result.exit_code == 1
    assert "unknown pack" in result.output


def test_run_executes_a_scenario_straight_from_a_pack(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "run", "--pack", "agentleak_bench", "--scenario", "agentleak_cor_00800",
            "--output", str(tmp_path), "--format", "json",
        ],
    )

    assert result.exit_code in (0, 1), result.output  # 1 = blocked verdict, still a success path
    assert "AgentLeak Privacy Report" in result.output
    written = list(tmp_path.glob("*.json"))
    assert written, "the run must produce a report"
    payload = json.loads(written[0].read_text(encoding="utf-8"))
    assert "risk_index" in payload


def test_run_rejects_an_unknown_scenario_in_a_pack() -> None:
    result = runner.invoke(app, ["run", "--pack", "agentleak_bench", "--scenario", "nope"])
    assert result.exit_code != 0
    assert "not found in pack" in result.output


# -- defenses have a door: `agentleak redact` ------------------------------
def test_redact_from_a_file(tmp_path: Path) -> None:
    target = tmp_path / "log.txt"
    target.write_text("Contact jane@acme.io about SSN 123-45-6789\n", encoding="utf-8")

    result = runner.invoke(app, ["redact", str(target)])

    assert result.exit_code == 0, result.output
    assert "jane@acme.io" not in result.output
    assert "123-45-6789" not in result.output
    assert "REDACTED" in result.output


def test_redact_writes_to_an_output_file(tmp_path: Path) -> None:
    target = tmp_path / "log.txt"
    target.write_text("ssn 123-45-6789\n", encoding="utf-8")
    out = tmp_path / "clean.txt"

    result = runner.invoke(app, ["redact", str(target), "--output", str(out)])

    assert result.exit_code == 0, result.output
    assert "123-45-6789" not in out.read_text(encoding="utf-8")


def test_redact_rejects_an_unknown_style(tmp_path: Path) -> None:
    target = tmp_path / "log.txt"
    target.write_text("hello\n", encoding="utf-8")

    result = runner.invoke(app, ["redact", str(target), "--style", "nonsense"])

    assert result.exit_code == 2
    assert "style must be one of" in result.output


def test_redact_reads_stdin() -> None:
    result = runner.invoke(app, ["redact"], input="ssn 123-45-6789\n")

    assert result.exit_code == 0, result.output
    assert "123-45-6789" not in result.output


# -- a report states its own strength (no quiet "Pass") --------------------
def test_report_declares_which_tiers_ran() -> None:
    from agentleak.core.runner import AgentLeakRunner
    from agentleak.scenarios import load_example_trace

    report = AgentLeakRunner().analyze(load_example_trace("healthcare_patient_summary")).to_dict()

    detection = report["detection"]
    assert detection["mode"] == "fast"
    assert detection["tiers"] == ["regex"], "a fast run must not imply deeper tiers ran"
    assert detection["degraded"] is False


def test_cli_shows_the_detection_tiers(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["run", "--scenario", "healthcare_patient_summary",
         "--output", str(tmp_path), "--format", "json"],
    )

    assert "Detection: fast mode · tiers: regex" in result.output
    assert "regex only" in result.output, "the weaker claim must be labelled as such"


# -- operator-side account recovery (no more locked-out-forever) ------------
def test_reset_password_replaces_the_password_and_revokes_sessions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTLEAK_HOME", str(tmp_path))
    from agentleak.core.store import Store

    store = Store()
    user = store.create_user("locked@out.io", "original-pass-123")
    token = store.create_session(user["id"])
    assert store.session_user(token) is not None

    assert store.reset_password("locked@out.io", "brand-new-pass-456") is True

    assert store.verify_user("locked@out.io", "original-pass-123") is None
    assert store.verify_user("locked@out.io", "brand-new-pass-456") is not None
    assert store.session_user(token) is None, "a stolen token must die with the reset"


def test_reset_password_is_case_insensitive_on_email(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTLEAK_HOME", str(tmp_path))
    from agentleak.core.store import Store

    store = Store()
    store.create_user("Mixed@Case.io", "original-pass-123")
    assert store.reset_password("  MIXED@case.io  ", "new-pass-456") is True


def test_reset_password_reports_an_unknown_account(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTLEAK_HOME", str(tmp_path))
    from agentleak.core.store import Store

    assert Store().reset_password("ghost@nowhere.io", "whatever-123") is False


def test_cli_admin_reset_password(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTLEAK_HOME", str(tmp_path))
    from agentleak.core.store import Store

    Store().create_user("locked@out.io", "original-pass-123")

    result = runner.invoke(
        app, ["admin", "reset-password", "locked@out.io", "--password", "brand-new-pass-456"]
    )

    assert result.exit_code == 0, result.output
    assert "password reset" in result.output
    assert Store().verify_user("locked@out.io", "brand-new-pass-456") is not None


def test_cli_admin_reset_password_rejects_a_short_password(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTLEAK_HOME", str(tmp_path))
    from agentleak.core.store import Store

    Store().create_user("locked@out.io", "original-pass-123")
    result = runner.invoke(app, ["admin", "reset-password", "locked@out.io", "--password", "short"])

    assert result.exit_code == 2
    assert "at least 8 characters" in result.output


def test_cli_admin_reset_password_unknown_account(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENTLEAK_HOME", str(tmp_path))
    result = runner.invoke(
        app, ["admin", "reset-password", "ghost@nowhere.io", "--password", "whatever-123"]
    )
    assert result.exit_code == 1
    assert "no account with email" in result.output
