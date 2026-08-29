# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""``agentleak scan`` must point at the line that holds the problem.

An eight-line agent that leaks three ways was scanned, and the report got all
three wrong:

    5  logger.info(f"Processing patient {patient['name']} SIN={patient['sin']}")
    6  memory.save({"diagnosis": patient["diagnosis"], "mrn": patient["mrn"]})
    7  send_to_vendor(api_key=os.environ["STRIPE_KEY"], payload=patient)

Three L4 findings landed on line 5 — sin, health_identifier, health_condition —
each showing line 5 as its evidence. Line 5 contains no diagnosis and no MRN.
The key-name detector, reading source instead of a trace, had captured the
string ``patient[`` out of ``SIN={patient['sin']}`` and reported *a bracket* as
a leaked identifier; every occurrence resolved to the first ``patient[`` in the
file, which is on line 5.

Meanwhile the two lines that matter went unreported. Line 6 writes a diagnosis
into agent memory, the channel this project exists to audit. Line 7 sends a
credential and a whole patient record to a third party in one call — the shape
behind this year's MCP incidents.

This matters past the terminal: the GitHub Action annotates PR lines. A gate
that flags a line with nothing on it, three times, while missing the export, is
a gate somebody turns off.
"""

from __future__ import annotations

from agentleak.core.codescan import scan_files

LEAKY_AGENT = (
    "import logging, os\n"
    "logger = logging.getLogger(__name__)\n"
    "\n"
    "def handle(patient):\n"
    "    logger.info(f\"Processing patient {patient['name']} SIN={patient['sin']}\")\n"
    "    memory.save({\"diagnosis\": patient[\"diagnosis\"], \"mrn\": patient[\"mrn\"]})\n"
    "    send_to_vendor(api_key=os.environ[\"STRIPE_KEY\"], payload=patient)\n"
    "    return \"Done\"\n"
)


def _scan(code: str = LEAKY_AGENT):
    return scan_files({"leaky_agent.py": code})


# ----------------------------------------------------------------------
# No phantom secrets
# ----------------------------------------------------------------------
def test_a_code_expression_is_not_a_leaked_secret() -> None:
    findings = _scan().findings
    phantoms = [f for f in findings if "[" in f.data_type or f.rule == "pii_in_code"]
    assert not phantoms, (
        "the key-name detector reported the expression 'patient[' as a leaked "
        f"SIN, diagnosis and health identifier: {[(f.rule, f.data_type) for f in phantoms]}"
    )


def test_an_email_literal_is_still_a_leak() -> None:
    """The narrow guard exists so this keeps working. 'Looks like attribute
    access' would have described every email address in every fixture.
    """
    result = scan_files({"fixtures.py": '"email": "jane.doe@acme.com",\n'})
    assert [f for f in result.findings if f.data_type == "email"]


# ----------------------------------------------------------------------
# Every finding on its own line, with its own evidence
# ----------------------------------------------------------------------
def test_each_finding_points_at_the_line_that_holds_it() -> None:
    for finding in _scan().findings:
        if finding.tier == "correlation":
            continue  # a file-level observation, legitimately line 1
        source_line = LEAKY_AGENT.split("\n")[finding.line - 1]
        assert finding.snippet.strip()[:20] in source_line or source_line.strip(), (
            f"{finding.rule} claims line {finding.line}"
        )


def test_the_memory_write_is_reported_on_its_own_line() -> None:
    memory = [f for f in _scan().findings if f.rule == "sensitive_to_memory"]
    assert memory, "a diagnosis written to agent memory went unreported"
    assert memory[0].line == 6
    assert "memory.save" in memory[0].snippet


def test_the_credentialed_export_is_reported_on_its_own_line() -> None:
    export = [f for f in _scan().findings if f.rule == "credentialed_record_export"]
    assert export, (
        "a credential and a full patient record left in one call and nothing "
        "flagged it — the pattern behind this year's MCP incidents"
    )
    assert export[0].line == 7
    assert export[0].level == 4


def test_the_log_line_keeps_its_own_finding() -> None:
    logs = [f for f in _scan().findings if f.rule == "log_sensitive"]
    assert logs and logs[0].line == 5


def test_a_repeated_value_is_reported_at_every_line_it_appears_on() -> None:
    """Reporting only the first occurrence sent the reviewer to one line and
    left the others unannotated, which is the same defect seen from the other
    side.
    """
    code = (
        'first = "jane.doe@acme.com"\n'
        'second = "jane.doe@acme.com"\n'
    )
    lines = {f.line for f in scan_files({"dup.py": code}).findings if f.data_type == "email"}
    assert lines == {1, 2}


# ----------------------------------------------------------------------
# The new rules must not fire on ordinary code
# ----------------------------------------------------------------------
def test_a_credential_alone_is_not_an_export() -> None:
    result = scan_files({"ok.py": "client = Vendor(api_key=os.environ['KEY'])\n"})
    assert not [f for f in result.findings if f.rule == "credentialed_record_export"]


def test_a_payload_alone_is_not_an_export() -> None:
    result = scan_files({"ok.py": "send(payload=summary)\n"})
    assert not [f for f in result.findings if f.rule == "credentialed_record_export"]


def test_a_memory_write_without_sensitive_fields_is_not_flagged() -> None:
    result = scan_files({"ok.py": 'memory.save({"case_id": case_id, "step": 3})\n'})
    assert not [f for f in result.findings if f.rule == "sensitive_to_memory"]
