"""Tests for the static code privacy scanner (core/codescan.py)."""

from __future__ import annotations

import base64
import io
import zipfile

import pytest

from agentleak.core.codescan import (
    CodeScanResult,
    scan_dir,
    scan_files,
    scan_payload,
    scan_text,
    scan_zip_bytes,
)

LEAKY_AGENT = '''
import logging
import requests

logger = logging.getLogger(__name__)

API_KEY = "sk-proj-abcdef1234567890abcdef1234567890"

def handle(customer):
    password = "hunter2secret99"
    logger.info(f"processing ssn={customer.ssn}")
    print("card:", customer.credit_card)
    requests.post("https://crm.example.com", json={"ssn": customer.ssn})
'''

CLEAN_AGENT = '''
import logging

logger = logging.getLogger(__name__)

def handle(customer):
    logger.info("processing customer request")
    return "done"
'''


def test_scan_text_detects_leaky_patterns():
    findings = scan_text("agent.py", LEAKY_AGENT)
    rules = {f.rule for f in findings}
    assert "log_sensitive" in rules          # logger.info(...ssn...)
    assert "print_sensitive" in rules        # print(...credit_card...)
    assert "sensitive_to_http" in rules      # requests.post(...ssn...)
    assert "hardcoded_credential_assignment" in rules or "hardcoded_secret" in rules
    # Levels are within the AgentRisk 1..4 band.
    assert all(1 <= f.level <= 4 for f in findings)


def test_snippets_are_redacted():
    findings = scan_text("agent.py", 'password = "supersecretvalue123"')
    for f in findings:
        assert "supersecretvalue123" not in f.snippet


def test_clean_file_scores_100():
    result = scan_files({"agent.py": CLEAN_AGENT})
    assert result.findings == []
    assert result.score == 100
    assert result.verdict == "Pass"


def test_leaky_files_lower_score_monotonically():
    clean = scan_files({"agent.py": CLEAN_AGENT})
    leaky = scan_files({"agent.py": LEAKY_AGENT})
    assert leaky.score < clean.score
    assert leaky.summary()["total_findings"] > 0


def test_env_committed_rule():
    result = scan_files({".env": "OPENAI_API_KEY=sk-live-abcdef123456\n"})
    assert any(f.rule == "env_committed" and f.level == 4 for f in result.findings)
    # Example env files are fine.
    ok = scan_files({".env.example": "OPENAI_API_KEY=<your-key-here>\n"})
    assert not any(f.rule == "env_committed" for f in ok.findings)


def test_placeholder_credentials_not_flagged():
    result = scan_files({"conf.py": 'password = "${DB_PASSWORD}"\napi_key = "your-api-key-here"'})
    assert not any(f.rule == "hardcoded_credential_assignment" for f in result.findings)


def test_skips_vendored_and_binary_paths():
    result = scan_files({
        "node_modules/lib/index.js": 'password = "hunter2secret99"',
        ".git/config": 'password = "hunter2secret99"',
        "photo.png": "binary-ish",
    })
    assert result.files_scanned == 0
    assert result.files_skipped == 3


def _make_zip(entries: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_scan_zip_bytes_github_layout_and_zip_slip():
    blob = _make_zip({
        "repo-main/agent.py": LEAKY_AGENT,          # nested like a GitHub archive
        "repo-main/../evil.py": 'password = "x"',   # traversal — must be skipped
    })
    result = scan_zip_bytes(blob, source_ref="acme/repo@main")
    assert result.source_type == "zip"
    assert result.files_scanned == 1
    assert any(f.file == "agent.py" for f in result.findings)


def test_scan_zip_rejects_garbage():
    with pytest.raises(ValueError):
        scan_zip_bytes(b"not a zip at all")


def test_scan_dir(tmp_path):
    (tmp_path / "agent.py").write_text(LEAKY_AGENT)
    sub = tmp_path / "node_modules"
    sub.mkdir()
    (sub / "dep.py").write_text(LEAKY_AGENT)
    result = scan_dir(tmp_path)
    assert result.files_scanned == 1
    assert result.source_type == "dir"
    with pytest.raises(ValueError):
        scan_dir(tmp_path / "nope")


def test_scan_payload_files_and_zip_and_errors():
    res = scan_payload({"source": "files", "files": [{"path": "a.py", "content": LEAKY_AGENT}]})
    assert isinstance(res, CodeScanResult)
    assert res.files_scanned == 1

    blob = base64.b64encode(_make_zip({"r-main/a.py": CLEAN_AGENT})).decode()
    res = scan_payload({"source": "zip", "data": blob})
    assert res.score == 100

    with pytest.raises(ValueError):
        scan_payload({"source": "zip", "data": "!!!not-base64!!!"})
    with pytest.raises(ValueError):
        scan_payload({"source": "files", "files": []})
    with pytest.raises(ValueError):
        scan_payload({"source": "github"})  # missing repo
    with pytest.raises(ValueError):
        scan_payload({"source": "ftp"})


def test_scan_github_repo_mocked(monkeypatch):
    from agentleak.core import codescan

    blob = _make_zip({"bot-main/agent.py": LEAKY_AGENT})
    monkeypatch.setattr(codescan, "fetch_github_repo", lambda repo, **kw: blob)
    result = codescan.scan_github_repo("acme/bot")
    assert result.source_type == "github"
    assert result.findings


def test_github_repo_name_validation():
    from agentleak.core.codescan import fetch_github_repo

    with pytest.raises(ValueError):
        fetch_github_repo("not a repo name !!!")


# ----------------------------------------------------------------------
# Robust detection: decomposed PII, entropy, lexicon, tiers, combinations
# ----------------------------------------------------------------------
def test_decomposed_concatenated_ssn_is_caught():
    """SSN split across concatenated string literals re-forms and is detected."""
    code = 'ssn = "123" + "-45-" + "6789"\n'
    result = scan_files({"a.py": code})
    hits = [f for f in result.findings if f.data_type == "ssn"]
    assert hits, "concatenation-joined variant must catch the split SSN"
    assert any(f.tier == "deobfuscation" or f.rule == "decomposed_pii" for f in hits)


def test_decomposed_spaced_ssn_with_context():
    """9 digits with unusual separators + SSN context keyword → finding."""
    code = 'user_ssn = "123 45 6789"  # social security number\n'
    result = scan_files({"a.py": code})
    assert any(f.rule == "decomposed_pii" and f.data_type == "ssn" for f in result.findings)


def test_decomposed_dotted_credit_card_luhn():
    """Dotted card number passes Luhn — no context keyword needed."""
    code = 'value = "4111.1111.1111.1111"\n'
    result = scan_files({"a.py": code})
    assert any(
        f.data_type == "credit_card" and f.level == 4 for f in result.findings
    ), "Luhn-valid decomposed card must be detected"


def test_random_digit_runs_not_flagged():
    """Digit runs without Luhn validity or context stay silent (precision)."""
    code = 'build = "2024 11 30 1234"\nversion = "10.20.30.40.50"\n'
    result = scan_files({"a.py": code})
    assert not any(f.rule == "decomposed_pii" for f in result.findings)


def test_entropy_detects_unknown_format_secret():
    """A secret with NO known key format is still caught by entropy."""
    code = 'blob = "gK9zQ2xW7vB4nM1pR8sT3uY6eH0jL5dF"\n'
    result = scan_files({"a.py": code})
    assert any(
        f.rule in ("high_entropy_string", "hardcoded_secret") for f in result.findings
    ), "high-entropy literal must be flagged even without a known format"


def test_entropy_ignores_paths_and_prose():
    code = (
        'p = "/usr/local/share/agentleak/static/assets"\n'
        'slug = "this-is-a-long-kebab-case-page-slug-here"\n'
        'key = "<YOUR-SECRET-GOES-HERE-REPLACE-ME-OK>"\n'
    )
    result = scan_files({"a.py": code})
    assert not any(f.rule == "high_entropy_string" for f in result.findings)


def test_french_lexicon_from_taxonomy():
    """The lexicon is generated (taxonomy + FR synonyms), not a short list."""
    code = (
        'logger.info(f"mot_de_passe={mdp}")\n'
        'print("numéro_assurance_sociale:", nas_val)\n'
    )
    result = scan_files({"a.py": code})
    rules = {f.rule for f in result.findings}
    assert "log_sensitive" in rules
    assert "print_sensitive" in rules


def test_extra_identifiers_extend_lexicon():
    """Deployments can extend the lexicon per scan — nothing is fixed."""
    code = 'logger.info(f"matricule={m}")\n'
    assert not any(
        f.rule == "log_sensitive" for f in scan_files({"a.py": code}).findings
    )
    result = scan_files({"a.py": code}, extra_identifiers=["matricule"])
    assert any(f.rule == "log_sensitive" for f in result.findings)


def test_benign_compounds_not_flagged():
    """healthcheck / tokenizer / 'since' never fire the sensitive lexicon."""
    code = (
        'logger.info("healthcheck ok")\n'
        'logger.debug("tokens processed: %d", n)\n'
        'logger.info("running since startup")\n'
        'console.log("health_check passed")\n'
    )
    result = scan_files({"a.js": code, "b.py": code})
    assert not any(f.rule == "log_sensitive" for f in result.findings), [
        f.snippet for f in result.findings
    ]


def test_quasi_identifier_combination_detected():
    """Several benign-looking PII types in one file → re-identification risk."""
    code = (
        '"email": "jane.doe@acme.com",\n'
        '"phone": "514-555-0142",\n'
        '"dob": "1987-03-14",\n'
        '"address": "12 Main Street",\n'
    )
    result = scan_files({"fixtures.py": code})
    combo = [f for f in result.findings if f.rule == "quasi_identifier_combination"]
    assert combo and combo[0].tier == "correlation"
    assert "email" in combo[0].snippet


def test_findings_carry_tier_and_confidence():
    result = scan_files({"a.py": LEAKY_AGENT})
    assert all(f.tier for f in result.findings)
    assert all(0.0 <= f.confidence <= 1.0 for f in result.findings)
    data = result.to_dict()
    assert data["detection"]["mode"] == "fast"
    assert "deobfuscation" in data["detection"]["tiers"]
    assert "by_tier" in data["summary"]


def test_config_detector_toggles_respected():
    """The scan honours the project's detector configuration."""
    from agentleak.core.config import Config

    code = 'contact = "jane@acme.com"\n'
    assert any(f.data_type == "email" for f in scan_files({"a.py": code}).findings)
    cfg = Config.from_dict({
        "detectors": {"pii": False, "secrets": True, "healthcare": False,
                      "finance": False, "hr": False},
    })
    result = scan_files({"a.py": code}, config=cfg)
    assert not any(f.data_type == "email" for f in result.findings)


def test_custom_detector_rules_apply_to_code():
    """Custom regex rules from agentleak.yaml run inside the code scan too."""
    from agentleak.core.config import Config

    cfg = Config.from_dict({
        "custom_detectors": [
            {"name": "employee_badge", "pattern": r"BADGE-\d{6}",
             "severity": "high", "data_type": "employee_badge"},
        ],
    })
    result = scan_files({"a.py": 'badge = "BADGE-482913"\n'}, config=cfg)
    assert any(f.data_type == "employee_badge" for f in result.findings)


def test_hybrid_mode_llm_judge_semantic_leak():
    """Tier 3: the LLM-judge catches paraphrased PII no regex can see."""
    from agentleak.core.codescan import CodeScanner
    from agentleak.core.detector import RawMatch, Severity
    from agentleak.core.pipeline import DetectionMode

    class FakeJudge:
        def detect(self, text):
            if "suffers from type-2 diabetes" in text:
                return [RawMatch(
                    data_type="health_condition", severity=Severity.HIGH,
                    confidence=0.9, matched_value="suffers from type-2 diabetes",
                    recommendation="Remove health details.", detector="llm_judge",
                )]
            return []

    scanner = CodeScanner()
    scanner.pipeline.mode = DetectionMode.HYBRID
    scanner.pipeline._llm_judge = FakeJudge()

    code = 'PROMPT = "the customer suffers from type-2 diabetes, be gentle"\n'
    findings = scanner.scan_text("prompt.py", code)
    semantic = [f for f in findings if f.rule == "semantic_leak"]
    assert semantic and semantic[0].tier == "semantic"
    assert semantic[0].data_type == "health_condition"
    assert semantic[0].level == 4  # health data is L4 in the taxonomy


def test_pipeline_mode_flows_from_config():
    """detection.mode in the config drives the pipeline mode (3-tier stack)."""
    from agentleak.core.codescan import CodeScanner
    from agentleak.core.config import Config

    cfg = Config.from_dict({"detection": {"mode": "standard", "presidio": {"enabled": True}}})
    scanner = CodeScanner(cfg)
    assert scanner.pipeline.mode.value == "standard"
    # Presidio may be absent (optional extra) — the pipeline degrades to
    # regex without error, exactly like the runtime analysis.
    result = scanner.scan_files({"a.py": 'x = "jane@acme.com"\n'})
    assert result.detection_mode == "standard"
