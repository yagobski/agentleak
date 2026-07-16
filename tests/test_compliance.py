"""Compliance framework mapping."""

from __future__ import annotations

from pathlib import Path

from agentleak import AgentLeakRunner, Trace
from agentleak.core.compliance import FRAMEWORKS
from agentleak.scenarios import load_example_trace

REPO_ROOT = Path(__file__).resolve().parent.parent

# Short, human-recognizable label for each framework, used to check that the
# docs/README haven't drifted from the actual set of implemented frameworks.
_SHORT_LABEL = {
    "gdpr": "GDPR",
    "law25": "Law 25",
    "nist_ai_rmf": "NIST AI RMF",
    "owasp_llm": "OWASP LLM",
    "eu_ai_act": "EU AI Act",
    "hipaa": "HIPAA",
    "pci_dss": "PCI-DSS",
}


def _report(trace: Trace) -> dict:
    return AgentLeakRunner().analyze(trace).to_dict()


def test_docs_and_readme_list_every_implemented_framework():
    """Regression guard: docs/compliance.md and README.md must mention every
    framework actually implemented in ``compliance.FRAMEWORKS`` (e.g. this
    caught HIPAA/PCI-DSS being implemented but missing from both docs).
    """
    docs_text = (REPO_ROOT / "docs" / "compliance.md").read_text(encoding="utf-8")
    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert set(_SHORT_LABEL) == {fw.id for fw in FRAMEWORKS}, (
        "add a short label above for any newly added framework"
    )
    for fw in FRAMEWORKS:
        label = _SHORT_LABEL[fw.id]
        assert label in docs_text, f"{fw.name} missing from docs/compliance.md"
        assert label in readme_text, f"{fw.name} missing from README.md"


def test_compliance_includes_machine_readable_disclaimer():
    """A ``disclaimer`` object is present alongside the human-readable prose
    in docs, so an agent/CI consumer doesn't have to parse markdown to learn
    a compliant result isn't legal certification.
    """
    c = _report(load_example_trace("hr_employee_case"))["compliance"]
    disclaimer = c["disclaimer"]
    assert disclaimer["is_legal_certification"] is False
    assert disclaimer["is_compliance_attestation"] is False
    assert "not" in disclaimer["text"].lower()
    assert disclaimer["scope"]


def test_compliance_disclaimer_present_regardless_of_verdict():
    # The disclaimer must appear whether the run is clean or leaky — it's not
    # conditioned on the compliance verdict.
    clean = Trace(run_id="clean")
    clean.add_event("final_output", "All good, nothing sensitive.")
    clean_compliance = _report(clean)["compliance"]
    leaky_compliance = _report(load_example_trace("healthcare_patient_summary"))["compliance"]
    assert clean_compliance["disclaimer"] == leaky_compliance["disclaimer"]


def test_clean_run_is_compliant():
    trace = Trace(run_id="clean")
    trace.add_event("final_output", "All good, nothing sensitive.")
    c = _report(trace)["compliance"]
    assert c["summary"]["non_compliant"] == 0
    assert all(fw["status"] == "compliant" for fw in c["frameworks"])


def test_health_leak_trips_gdpr_art9():
    c = _report(load_example_trace("healthcare_patient_summary"))["compliance"]
    gdpr = next(f for f in c["frameworks"] if f["id"] == "gdpr")
    art9 = next(ctrl for ctrl in gdpr["controls"] if ctrl["id"] == "gdpr.art9")
    assert art9["status"] == "at_risk"
    assert art9["evidence"]  # the health data types
    assert gdpr["status"] == "non_compliant"


def test_secret_leak_trips_gdpr_art32():
    trace = Trace(run_id="r")
    trace.add_event("log", "aws key AKIAIOSFODNN7EXAMPLE leaked")
    c = _report(trace)["compliance"]
    gdpr = next(f for f in c["frameworks"] if f["id"] == "gdpr")
    art32 = next(ctrl for ctrl in gdpr["controls"] if ctrl["id"] == "gdpr.art32")
    assert art32["status"] == "at_risk"


def test_nist_privacy_measured_is_info():
    c = _report(load_example_trace("finance_loan_review"))["compliance"]
    nist = next(f for f in c["frameworks"] if f["id"] == "nist_ai_rmf")
    measured = next(ctrl for ctrl in nist["controls"] if ctrl["id"] == "nist.measure2.7")
    assert measured["status"] == "info"


def test_all_frameworks_present():
    c = _report(load_example_trace("hr_employee_case"))["compliance"]
    ids = {f["id"] for f in c["frameworks"]}
    assert ids == {"gdpr", "law25", "nist_ai_rmf", "owasp_llm", "eu_ai_act", "hipaa", "pci_dss"}
    assert c["summary"]["total"] == 7


def test_health_leak_trips_hipaa():
    c = _report(load_example_trace("healthcare_patient_summary"))["compliance"]
    hipaa = next(f for f in c["frameworks"] if f["id"] == "hipaa")
    assert hipaa["status"] == "non_compliant"
    access = next(ctrl for ctrl in hipaa["controls"] if ctrl["id"] == "hipaa.164.312a")
    assert access["status"] == "at_risk"
    assert access["evidence"]


def test_card_leak_trips_pci_dss():
    trace = Trace(run_id="r")
    trace.add_event("log", "charging card 4111 1111 1111 1111 for the order")
    c = _report(trace)["compliance"]
    pci = next(f for f in c["frameworks"] if f["id"] == "pci_dss")
    assert pci["status"] == "non_compliant"
    req3 = next(ctrl for ctrl in pci["controls"] if ctrl["id"] == "pci.req3")
    assert req3["status"] == "at_risk"


def test_clean_run_passes_hipaa_and_pci():
    trace = Trace(run_id="clean")
    trace.add_event("final_output", "All good, nothing sensitive.")
    c = _report(trace)["compliance"]
    for fid in ("hipaa", "pci_dss"):
        fw = next(f for f in c["frameworks"] if f["id"] == fid)
        assert fw["status"] == "compliant"


def test_posture_digest_on_clean_run():
    trace = Trace(run_id="clean")
    trace.add_event("final_output", "All good, nothing sensitive.")
    posture = _report(trace)["compliance"]["posture"]
    assert posture["status"] == "compliant"
    assert posture["failed_frameworks"] == []


def test_posture_digest_on_leaky_run():
    posture = _report(load_example_trace("healthcare_patient_summary"))["compliance"]["posture"]
    assert posture["status"] == "non_compliant"
    assert "hipaa" in posture["failed_frameworks"]
    assert "gdpr" in posture["failed_frameworks"]
    # failed list is sorted by number of controls at risk (desc)
    counts = [f["at_risk"] for f in posture["failed"]]
    assert counts == sorted(counts, reverse=True)
