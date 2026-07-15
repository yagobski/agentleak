"""Static privacy scan of agent source code — powered by the same hybrid
detection pipeline as the runtime analysis.

The scanner is NOT a fixed list of regexes: every file is run through
AgentLeak's 3-tier :class:`~agentleak.core.pipeline.HybridPipeline`:

- **Tier 1+2 — regex detectors** (PII, secrets, healthcare, finance, HR,
  custom rules), always on;
- **Tier 2b — Presidio** (20+ recognizers) when installed and enabled;
- **Tier 3 — LLM-as-Judge** for paraphrased / inferred / semantic leaks when
  an endpoint is configured (``detection.mode: hybrid``).

On top of the pipeline, four code-specific layers close the gaps static
source code opens:

1. **Generated identifier lexicon** — sensitive identifier stems are derived
   from the AgentRisk data-type taxonomy plus an extended EN/FR synonym set,
   and are extensible per scan (``extra_identifiers``). Rules built from the
   lexicon flag sensitive variables flowing into logs, stdout, and outbound
   HTTP calls.
2. **Entropy analysis** (detect-secrets style) — high-entropy string literals
   are flagged as probable secrets even when no known key format matches.
3. **De-obfuscation** — string-concatenation joining and digit-run
   normalization catch *decomposed* PII (``"123" + "-45-" + "6789"``,
   ``123 45 6789``, dotted/underscored groups) with context keywords and
   Luhn validation.
4. **Quasi-identifier combination** — files that accumulate several distinct
   PII types are flagged for re-identification risk (GDPR Rec. 26) even when
   each element alone looks benign.

No detector is perfect in adversarial settings — that is precisely why the
tiers are layered and why findings carry their tier + confidence, so the
report is auditable instead of a black box. Matched values are redacted;
raw secrets are never persisted.

Sources: :func:`scan_files` (in-memory mapping), :func:`scan_dir`,
:func:`scan_zip_bytes` (zip-slip safe), :func:`scan_github_repo` (explicit
opt-in download via stdlib urllib).
"""

from __future__ import annotations

import fnmatch
import io
import json
import math
import re
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..detectors import build_detectors
from ..detectors.pii import _luhn_ok
from .agentrisk import DATA_TYPE_LEVELS, level_for
from .config import Config
from .detector import Severity, redact

# -- scan limits (defensive, keeps scans fast and memory-bounded) --------
MAX_FILE_BYTES = 512 * 1024
MAX_FILES = 2000
# Aggregate cap on DECLARED uncompressed size across a zip archive, checked
# before any entry is decompressed — a cheap first line of defense against
# zip-bomb archives (a tiny compressed file that expands to gigabytes).
MAX_ZIP_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
# Cap on a downloaded GitHub archive (compressed, streamed) so a huge or
# malicious repo can't exhaust memory during the opt-in network fetch.
MAX_GITHUB_DOWNLOAD_BYTES = 50 * 1024 * 1024

# Files worth scanning: code, config, docs and env files.
SCANNABLE_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs", ".java", ".go",
    ".rb", ".rs", ".php", ".sh", ".bash", ".zsh",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".md", ".txt", ".env", ".properties", ".xml", ".sql",
}
SCANNABLE_NAMES = {".env", "Dockerfile", "Makefile", "Procfile"}

# Paths never scanned (vendored deps, VCS internals, build output).
SKIP_DIR_PATTERNS = (
    "node_modules", ".git", ".venv", "venv", "__pycache__", "dist", "build",
    ".mypy_cache", ".pytest_cache", ".next", "coverage", "site-packages",
    ".tox", "vendor", "*.egg-info",
)

# ----------------------------------------------------------------------
# Identifier lexicon — GENERATED from the AgentRisk taxonomy, not hardcoded.
# ----------------------------------------------------------------------
# Extended stems: credential vocabulary, EN/FR synonyms, healthcare/finance/HR
# identifiers. Each entry is a regex fragment (word boundaries added later).
_EXTRA_IDENTIFIER_STEMS: tuple[str, ...] = (
    # credentials & auth
    r"passwd", r"pwd", r"secret\w*", r"credential\w*", r"auth[_-]?token",
    r"access[_-]?token", r"refresh[_-]?token", r"session[_-]?(?:key|token|id)",
    r"bearer", r"client[_-]?secret", r"signing[_-]?key", r"encryption[_-]?key",
    r"master[_-]?key", r"otp", r"totp", r"2fa[_-]?code", r"security[_-]?answer",
    # identity documents
    r"passport\w*", r"driver[_-]?licen[cs]e", r"national[_-]?id",
    r"tax[_-]?id", r"nino", r"nif",
    # payment
    r"cvv", r"cvc", r"card[_-]?number", r"routing[_-]?number",
    r"swift", r"iban", r"rib",
    # health
    r"patient[_-]?(?:id|name|record)", r"diagnos\w*", r"mrn",
    r"ramq", r"prescription\w*", r"treatment\w*", r"medical[_-]?\w+",
    r"health(?![_-]?check)\w*",
    # HR / finance
    r"salar\w*", r"wage\w*", r"compensation", r"payroll", r"bonus\w*",
    r"performance[_-]?review", r"termination",
    # contact / identity
    r"birth[_-]?date", r"birthdate", r"dob", r"home[_-]?address",
    r"postal[_-]?code", r"zip[_-]?code",
    # French (Law 25 / RGPD deployments)
    r"mot[_-]?de[_-]?passe", r"courriel\w*", r"t[ée]l[ée]phone",
    r"adresse\w*", r"naissance", r"salaire\w*", r"sant[ée]",
    r"dossier[_-]?m[ée]dical", r"assurance[_-]?sociale", r"nas",
    r"num[ée]ro[_-]?(?:de[_-]?)?(?:carte|compte|assurance|s[ée]cu\w*)",
    r"carte[_-]?(?:bancaire|de[_-]?cr[ée]dit)", r"diagnostic\w*",
)

# Benign compounds that must never fire (cheap post-filter on the match).
_BENIGN_CONTEXT_RE = re.compile(
    r"health[_-]?check|token(?:izer?|ization)|\bsin(?:gle|k|ce)\b",
    re.IGNORECASE,
)


def _identifier_alternation(extra: Sequence[str] = ()) -> str:
    """Build the sensitive-identifier alternation from the AgentRisk taxonomy
    (``DATA_TYPE_LEVELS``) + extended stems + caller-provided extras."""
    stems: set[str] = set(_EXTRA_IDENTIFIER_STEMS)
    for data_type in DATA_TYPE_LEVELS:
        stems.add(data_type.replace("_", "[_-]?"))
    for raw in extra:
        stems.add(re.escape(str(raw)))
    # Longest-first keeps the alternation deterministic.
    return "|".join(sorted(stems, key=len, reverse=True))


def _compile_code_rules(
    extra_identifiers: Sequence[str] = (),
) -> list[tuple[str, re.Pattern[str], str, Severity, str]]:
    """Code-flow rules built on the *generated* identifier lexicon."""
    ident = rf"\b(?:{_identifier_alternation(extra_identifiers)})(?![a-z])"
    return [
        (
            "log_sensitive",
            re.compile(
                rf"(?:logger|logging|log|console)\s*\.\s*"
                rf"(?:debug|info|warning|warn|error|exception|critical|log|print)\s*\(.{{0,160}}{ident}",
                re.IGNORECASE,
            ),
            "sensitive_in_logs",
            Severity.HIGH,
            "Never log sensitive variables — redact or drop them before logging (C6 log channel).",
        ),
        (
            "print_sensitive",
            re.compile(rf"\bprint\s*\(.{{0,160}}{ident}", re.IGNORECASE),
            "sensitive_in_logs",
            Severity.MEDIUM,
            "print() of sensitive variables ends up in stdout/log capture; remove or mask.",
        ),
        (
            "sensitive_to_http",
            re.compile(
                rf"(?:requests\.(?:get|post|put|patch)|urllib\.request|httpx\.|axios\.|fetch\s*\()"
                rf".{{0,200}}{ident}",
                re.IGNORECASE | re.DOTALL,
            ),
            "sensitive_to_third_party",
            Severity.HIGH,
            "Sensitive fields flow into an outbound HTTP call — strip or tokenize before external tools (C3 tool_call channel).",
        ),
        (
            "insecure_tls",
            re.compile(r"verify\s*=\s*False|rejectUnauthorized\s*:\s*false", re.IGNORECASE),
            "insecure_transport",
            Severity.MEDIUM,
            "TLS verification is disabled — sensitive data may transit unprotected (GDPR Art. 32).",
        ),
        (
            "hardcoded_credential_assignment",
            re.compile(
                rf"""{ident}[A-Za-z0-9_]*\s*[:=]\s*["'][^"'\s]{{8,}}["']""",
                re.IGNORECASE,
            ),
            "hardcoded_credential",
            Severity.HIGH,
            "Credential-looking literal assigned in code — move it to a secret manager or environment variable.",
        ),
    ]


# Placeholder values that make credential/entropy matches false positives.
_PLACEHOLDER_RE = re.compile(
    r"(?:\$\{|\{\{|%\(|^<.+>$|^(?:xxx+|placeholder|change[-_]?me|your[-_]|dummy|sample|"
    r"example|test|fake|redacted|none|null|todo|fixme|lorem)|\*{3,})",
    re.IGNORECASE,
)

# ----------------------------------------------------------------------
# Entropy analysis (detect-secrets style)
# ----------------------------------------------------------------------
_STRING_LITERAL_RE = re.compile(r"""["']([A-Za-z0-9+/=_\-.]{20,})["']""")
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
_ENTROPY_BASE64_THRESHOLD = 4.5
_ENTROPY_HEX_THRESHOLD = 3.2


def shannon_entropy(value: str) -> float:
    """Shannon entropy in bits/char — the classic secret-detection signal."""
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(value)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _looks_like_secret(value: str) -> bool:
    """Entropy + charset classification, with common false-positive filters."""
    if _PLACEHOLDER_RE.search(value):
        return False
    # URLs, paths, dotted module names, kebab/snake prose: not secrets.
    if value.startswith(("http://", "https://", "/", "./")) or value.count("/") >= 3:
        return False
    if value.count(".") >= 3 or value.count("-") >= 6 or value.count("_") >= 6:
        return False
    if _HEX_RE.match(value):
        return shannon_entropy(value) >= _ENTROPY_HEX_THRESHOLD
    return shannon_entropy(value) >= _ENTROPY_BASE64_THRESHOLD


# ----------------------------------------------------------------------
# De-obfuscation — decomposed / reformatted PII
# ----------------------------------------------------------------------
# Digit runs with separators: 8–19 digits split by spaces/dashes/dots/etc.
_DIGIT_RUN_RE = re.compile(r"\d(?:[\d \t\-._/\\]{6,30}\d)")
_SSN_CONTEXT_RE = re.compile(r"ssn|\bsin\b|social|\bnas\b|assurance", re.IGNORECASE)
_PHONE_CONTEXT_RE = re.compile(r"phone|\btel\b|mobile|cell|fax|t[ée]l[ée]phone", re.IGNORECASE)

# String-literal concatenation joining: "123" + "-45" / "123" "-45" / '12','34'
_CONCAT_RE = re.compile(r"""["']\s*(?:\+|\.|,)?\s*["']""")


def join_concatenations(text: str) -> str:
    """Merge adjacent/concatenated string literals so split values re-form.

    ``"123" + "-45-" + "6789"`` → ``"123-45-6789"`` — the joined variant is
    then run through the full detection pipeline.
    """
    return _CONCAT_RE.sub("", text)


# ----------------------------------------------------------------------
# Findings & results
# ----------------------------------------------------------------------
@dataclass
class CodeFinding:
    """One static-analysis hit inside a source file."""

    file: str
    line: int
    rule: str
    data_type: str
    severity: Severity
    level: int
    snippet: str
    recommendation: str = ""
    tier: str = "regex"
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "rule": self.rule,
            "data_type": self.data_type,
            "severity": self.severity.value,
            "level": self.level,
            "snippet": self.snippet,
            "recommendation": self.recommendation,
            "tier": self.tier,
            "confidence": round(self.confidence, 3),
        }


@dataclass
class CodeScanResult:
    """Aggregated result of a static code scan."""

    findings: list[CodeFinding] = field(default_factory=list)
    files_scanned: int = 0
    files_skipped: int = 0
    source_type: str = "files"
    source_ref: str = ""
    detection_mode: str = "fast"
    tiers: list[str] = field(default_factory=lambda: ["regex"])
    generated_at: float = field(default_factory=time.time)

    @property
    def score(self) -> int:
        """0–100 code-privacy score (100 = clean), weighted by L1–L4 level."""
        if not self.findings:
            return 100
        weight = sum(f.level for f in self.findings)
        # 25 level-points ≈ a fully red scan; closed-form and monotonic.
        return max(0, round(100 * (1 - min(1.0, weight / 25.0))))

    @property
    def verdict(self) -> str:
        s = self.score
        if s >= 90:
            return "Pass"
        if s >= 70:
            return "Conditional pass"
        if s >= 40:
            return "High risk"
        return "Fail"

    def summary(self) -> dict[str, Any]:
        by_rule: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        by_level = {1: 0, 2: 0, 3: 0, 4: 0}
        for f in self.findings:
            by_rule[f.rule] = by_rule.get(f.rule, 0) + 1
            by_tier[f.tier] = by_tier.get(f.tier, 0) + 1
            by_level[f.level] = by_level.get(f.level, 0) + 1
        return {
            "total_findings": len(self.findings),
            "files_scanned": self.files_scanned,
            "files_skipped": self.files_skipped,
            "by_rule": by_rule,
            "by_tier": by_tier,
            "level_profile": {f"L{n}": by_level[n] for n in (1, 2, 3, 4)},
            "score": self.score,
            "verdict": self.verdict,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "scan": "agentleak-code",
            "version": 2,
            "source_type": self.source_type,
            "source_ref": self.source_ref,
            "generated_at": self.generated_at,
            "detection": {"mode": self.detection_mode, "tiers": list(self.tiers)},
            "score": self.score,
            "verdict": self.verdict,
            "summary": self.summary(),
            "findings": [f.to_dict() for f in self.findings],
        }


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _is_scannable(path: str) -> bool:
    parts = Path(path).parts
    for part in parts[:-1]:
        if any(fnmatch.fnmatch(part, pat) for pat in SKIP_DIR_PATTERNS):
            return False
    p = Path(path)
    return (
        p.suffix.lower() in SCANNABLE_SUFFIXES
        or p.name in SCANNABLE_NAMES
        or p.name.startswith(".env")
    )


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _snippet(text: str, index: int, matched: str) -> str:
    """The matched line, with the sensitive value redacted."""
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    line = text[start : end if end != -1 else len(text)].strip()
    if matched and matched in line:
        line = line.replace(matched, redact(matched))
    return line[:200]


def _decomposed_digit_findings(path: str, text: str) -> list[CodeFinding]:
    """Digit-run analysis: catches PII written with unusual separators or
    split into groups (``123 45 6789``, ``4111.1111.1111.1111``)."""
    findings: list[CodeFinding] = []
    for m in _DIGIT_RUN_RE.finditer(text):
        run = m.group(0)
        digits = re.sub(r"\D", "", run)
        context = text[max(0, m.start() - 80): m.end() + 80]
        data_type: str | None = None
        severity = Severity.HIGH
        confidence = 0.7
        if len(digits) in (13, 14, 15, 16) and _luhn_ok(digits):
            data_type, severity, confidence = "credit_card", Severity.CRITICAL, 0.9
        elif len(digits) == 9 and _SSN_CONTEXT_RE.search(context):
            low = context.lower()
            data_type = "ssn" if ("ssn" in low or "social" in low) else "sin"
            severity, confidence = Severity.HIGH, 0.8
        elif len(digits) in (10, 11) and _PHONE_CONTEXT_RE.search(context):
            data_type, severity, confidence = "phone_number", Severity.MEDIUM, 0.6
        if data_type is None:
            continue
        findings.append(CodeFinding(
            file=path,
            line=_line_of(text, m.start()),
            rule="decomposed_pii",
            data_type=data_type,
            severity=severity,
            level=level_for(data_type, severity),
            snippet=_snippet(text, m.start(), run.strip()),
            recommendation=(
                "PII written with unusual separators or split into fragments is still PII — "
                "remove it from source code (reformatting does not anonymize)."
            ),
            tier="deobfuscation",
            confidence=confidence,
        ))
    return findings


# PII-ish data types that count toward quasi-identifier accumulation
# (credentials excluded: a key + an email is not a re-identification risk).
_QUASI_ELIGIBLE = {
    dt for dt, lvl in DATA_TYPE_LEVELS.items()
    if lvl >= 2 and dt not in {
        "private_key", "aws_access_key", "github_token", "slack_token",
        "stripe_key", "jwt", "connection_string", "secret_assignment", "api_key",
    }
} | {"person_name"}


# ----------------------------------------------------------------------
# The scanner
# ----------------------------------------------------------------------
class CodeScanner:
    """Multi-tier static scanner sharing the runtime detection stack.

    Args:
        config: An AgentLeak :class:`Config`. Its ``detectors`` toggles,
            ``custom_detectors`` rules, ``scoring.level_overrides`` and
            ``detection`` block (mode / Presidio / LLM-judge) all apply —
            the code scan honours exactly the same settings as trace analysis.
            ``None`` = every built-in detector, FAST mode.
        extra_identifiers: Additional sensitive identifier stems (plain
            strings) merged into the generated lexicon.
    """

    def __init__(
        self,
        config: Config | None = None,
        *,
        extra_identifiers: Sequence[str] = (),
    ) -> None:
        from .runner import _build_pipeline  # single pipeline seam, no duplication

        if config is not None:
            detectors = build_detectors(config.detectors.as_dict(), config.custom_rules_raw())
            self._level_overrides = dict(config.scoring.level_overrides)
        else:
            detectors = build_detectors(None, None)
            self._level_overrides = {}
        self.pipeline = _build_pipeline(config, detectors)
        self.rules = _compile_code_rules(extra_identifiers)

    # -- single file ----------------------------------------------------
    def scan_text(self, path: str, text: str) -> list[CodeFinding]:
        """All findings for one file: pipeline tiers + code-specific layers."""
        findings: list[CodeFinding] = []
        seen: set[tuple[str, str]] = set()

        def _add(f: CodeFinding, key_value: str) -> None:
            normalized = re.sub(r"\D", "", key_value)
            key = (f.data_type, normalized if len(normalized) >= 7 else key_value)
            if key in seen:
                return
            seen.add(key)
            findings.append(f)

        # Layer 0 — committed env file with populated values.
        name = Path(path).name
        if name.startswith(".env") and not name.endswith((".example", ".sample", ".template")):
            if re.search(r"^[A-Z0-9_]+\s*=\s*\S{8,}", text, re.MULTILINE):
                _add(CodeFinding(
                    file=path, line=1, rule="env_committed",
                    data_type="hardcoded_credential", severity=Severity.CRITICAL,
                    level=4, snippet=f"{name} contains populated values",
                    recommendation="Never commit populated .env files — add them to .gitignore and rotate any exposed keys.",
                    tier="structural",
                ), name)

        # Layers 1–3 — the hybrid pipeline (regex / Presidio / LLM-judge) on
        # the raw text AND the concatenation-joined variant (split literals).
        variants = [("raw", text)]
        joined = join_concatenations(text)
        if joined != text:
            variants.append(("joined", joined))
        for variant_name, variant_text in variants:
            for f in self.pipeline.run_event(
                text=variant_text,
                event_id=path,
                run_id="codescan",
                channel="log",  # code at rest ≈ a log-tier surface
            ):
                tier = str(f.metadata.get("tier", "regex"))
                idx = text.find(f.matched_value)
                deobfuscated = variant_name == "joined" and idx < 0
                rule = (
                    "decomposed_pii" if deobfuscated
                    else "hardcoded_secret" if f.detector == "secrets_detector"
                    else "semantic_leak" if tier == "semantic"
                    else "pii_in_code"
                )
                _add(CodeFinding(
                    file=path,
                    line=_line_of(text, idx) if idx >= 0 else 1,
                    rule=rule,
                    data_type=f.data_type,
                    severity=f.severity,
                    level=f.level,
                    snippet=_snippet(text, idx, f.matched_value) if idx >= 0 else f.redacted_value,
                    recommendation=f.recommendation or "Remove literal sensitive values from source code.",
                    tier="deobfuscation" if deobfuscated else tier,
                    confidence=f.confidence,
                ), f.matched_value)

        # Layer 4 — digit-run de-obfuscation (decomposed PII).
        for digit_finding in _decomposed_digit_findings(path, text):
            _add(digit_finding, digit_finding.snippet)

        # Layer 5 — code-flow rules on the generated lexicon.
        for rule_id, pattern, data_type, severity, advice in self.rules:
            for m in pattern.finditer(text):
                matched = m.group(0)
                if _BENIGN_CONTEXT_RE.search(matched):
                    continue
                literal_value = ""
                literal = re.search(r"""["']([^"']+)["']\s*$""", matched)
                if literal:
                    literal_value = literal.group(1)
                if rule_id == "hardcoded_credential_assignment":
                    if literal_value and _PLACEHOLDER_RE.search(literal_value):
                        continue
                _add(CodeFinding(
                    file=path,
                    line=_line_of(text, m.start()),
                    rule=rule_id,
                    data_type=data_type,
                    severity=severity,
                    level=level_for(data_type, severity, self._level_overrides),
                    snippet=_snippet(text, m.start(), literal_value),
                    recommendation=advice,
                    tier="code_rule",
                ), f"{rule_id}:{_line_of(text, m.start())}")

        # Layer 6 — entropy analysis: unknown-format secrets.
        for m in _STRING_LITERAL_RE.finditer(text):
            value = m.group(1)
            if not _looks_like_secret(value):
                continue
            _add(CodeFinding(
                file=path,
                line=_line_of(text, m.start()),
                rule="high_entropy_string",
                data_type="secret_assignment",
                severity=Severity.HIGH,
                level=level_for("secret_assignment", Severity.HIGH, self._level_overrides),
                snippet=_snippet(text, m.start(), value),
                recommendation=(
                    "High-entropy literal — probable secret or token even though no known "
                    "key format matches. Move it out of source code and rotate it."
                ),
                tier="entropy",
                confidence=0.7,
            ), value)

        # Layer 7 — quasi-identifier accumulation (re-identification risk).
        pii_types = {f.data_type for f in findings if f.data_type in _QUASI_ELIGIBLE}
        if len(pii_types) >= 3:
            findings.append(CodeFinding(
                file=path,
                line=1,
                rule="quasi_identifier_combination",
                data_type="quasi_identifier",
                severity=Severity.HIGH,
                level=3,
                snippet="Combined: " + ", ".join(sorted(pii_types)),
                recommendation=(
                    "This file accumulates several distinct PII types — together they can "
                    "re-identify a person even if each looks benign (GDPR Rec. 26). "
                    "Split fixtures, use synthetic data, or a vault."
                ),
                tier="correlation",
                confidence=0.85,
            ))

        return findings

    # -- collections ------------------------------------------------------
    def scan_files(
        self,
        files: dict[str, str],
        *,
        source_type: str = "files",
        source_ref: str = "",
    ) -> CodeScanResult:
        result = CodeScanResult(
            source_type=source_type,
            source_ref=source_ref,
            detection_mode=self.pipeline.mode.value,
            tiers=self.pipeline.finding_tiers + ["deobfuscation", "entropy", "correlation"],
        )
        for path, content in list(files.items())[:MAX_FILES]:
            if not _is_scannable(path) or not isinstance(content, str):
                result.files_skipped += 1
                continue
            if len(content.encode("utf-8", errors="replace")) > MAX_FILE_BYTES:
                result.files_skipped += 1
                continue
            result.files_scanned += 1
            result.findings.extend(self.scan_text(path, content))
        result.findings.sort(key=lambda f: (-f.level, f.file, f.line))
        return result


# ----------------------------------------------------------------------
# Module-level entry points (backward compatible; config optional)
# ----------------------------------------------------------------------
def scan_files(
    files: dict[str, str],
    *,
    source_type: str = "files",
    source_ref: str = "",
    config: Config | None = None,
    extra_identifiers: Sequence[str] = (),
) -> CodeScanResult:
    """Scan an in-memory ``{path: content}`` mapping. The core entry point."""
    scanner = CodeScanner(config, extra_identifiers=extra_identifiers)
    return scanner.scan_files(files, source_type=source_type, source_ref=source_ref)


def scan_text(path: str, text: str, *, config: Config | None = None) -> list[CodeFinding]:
    """All code findings for one file's content."""
    return CodeScanner(config).scan_text(path, text)


def scan_dir(root: str | Path, *, config: Config | None = None) -> CodeScanResult:
    """Scan a local directory tree (respects skip patterns and size limits)."""
    root = Path(root)
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if len(files) >= MAX_FILES or not path.is_file():
            continue
        rel = str(path.relative_to(root))
        if not _is_scannable(rel):
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            files[rel] = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    return scan_files(files, source_type="dir", source_ref=str(root), config=config)


def scan_zip_bytes(
    data: bytes, *, source_ref: str = "", config: Config | None = None
) -> CodeScanResult:
    """Scan an uploaded zip archive fully in memory (zip-slip safe: nothing
    is ever extracted to disk; entries with traversal components are skipped).

    Rejects archives whose DECLARED total uncompressed size exceeds
    :data:`MAX_ZIP_UNCOMPRESSED_BYTES` *before* decompressing anything — a
    defensive check against zip-bomb archives.
    """
    files: dict[str, str] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = [i for i in zf.infolist() if not i.is_dir()]
            declared_total = sum(i.file_size for i in infos)
            if declared_total > MAX_ZIP_UNCOMPRESSED_BYTES:
                raise ValueError(
                    f"Archive declares {declared_total} uncompressed bytes, over the "
                    f"{MAX_ZIP_UNCOMPRESSED_BYTES} limit — refusing to decompress (zip-bomb guard)."
                )
            for info in infos:
                if len(files) >= MAX_FILES:
                    continue
                name = info.filename
                if name.startswith("/") or ".." in Path(name).parts:
                    continue  # path traversal — never trust archive paths
                # GitHub archives nest everything under "<repo>-<ref>/".
                parts = Path(name).parts
                rel = str(Path(*parts[1:])) if len(parts) > 1 else name
                if not _is_scannable(rel) or info.file_size > MAX_FILE_BYTES:
                    continue
                files[rel] = zf.read(info).decode("utf-8", errors="replace")
    except zipfile.BadZipFile as exc:
        raise ValueError("Uploaded file is not a valid zip archive.") from exc
    return scan_files(files, source_type="zip", source_ref=source_ref, config=config)


def fetch_github_repo(
    repo: str,
    *,
    branch: str = "main",
    token: str = "",
    timeout: float = 30.0,
) -> bytes:
    """Download a GitHub repo archive (zip) — explicit opt-in network call.

    ``repo`` is ``owner/name``. Uses the codeload endpoint via stdlib urllib.
    A token is only needed for private repositories and is sent as a header,
    never stored. The download is streamed and capped at
    :data:`MAX_GITHUB_DOWNLOAD_BYTES` so a huge or malicious repo can't
    exhaust memory.
    """
    repo = repo.strip().strip("/")
    # Accept a full URL and reduce it to owner/name.
    m = re.match(r"^https?://github\.com/([\w.-]+/[\w.-]+?)(?:\.git)?/?$", repo)
    if m:
        repo = m.group(1)
    if not re.match(r"^[\w.-]+/[\w.-]+$", repo):
        raise ValueError("Repository must be 'owner/name' or a github.com URL.")
    url = f"https://codeload.github.com/{repo}/zip/refs/heads/{branch}"
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_GITHUB_DOWNLOAD_BYTES:
                    raise ValueError(
                        f"Repository archive exceeds the {MAX_GITHUB_DOWNLOAD_BYTES}-byte download limit."
                    )
                chunks.append(chunk)
            return b"".join(chunks)
    except urllib.error.HTTPError as exc:
        raise ValueError(
            f"GitHub returned {exc.code} for {repo}@{branch} — check the repo, branch, and token."
        ) from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not reach GitHub: {exc.reason}") from exc


def scan_github_repo(
    repo: str,
    *,
    branch: str = "main",
    token: str = "",
    timeout: float = 30.0,
    config: Config | None = None,
) -> CodeScanResult:
    """Download and scan a GitHub repository in one call."""
    data = fetch_github_repo(repo, branch=branch, token=token, timeout=timeout)
    result = scan_zip_bytes(data, source_ref=f"{repo}@{branch}", config=config)
    result.source_type = "github"
    return result


def scan_payload(payload: dict[str, Any], *, config: Config | None = None) -> CodeScanResult:
    """Dispatch a scan request payload (shared by web API and clients).

    Supported shapes::

        {"source": "github", "repo": "owner/name", "branch": "main", "token": "..."}
        {"source": "zip", "data": "<base64 zip>"}
        {"source": "files", "files": [{"path": "agent.py", "content": "..."}]}
    """
    source = str(payload.get("source") or "files")
    if source == "github":
        repo = str(payload.get("repo") or "")
        if not repo:
            raise ValueError("'repo' is required for a GitHub scan.")
        return scan_github_repo(
            repo,
            branch=str(payload.get("branch") or "main"),
            token=str(payload.get("token") or ""),
            config=config,
        )
    if source == "zip":
        import base64

        raw = payload.get("data")
        if not isinstance(raw, str) or not raw:
            raise ValueError("'data' (base64 zip) is required for a zip scan.")
        try:
            blob = base64.b64decode(raw, validate=True)
        except Exception as exc:  # noqa: BLE001
            raise ValueError("'data' is not valid base64.") from exc
        return scan_zip_bytes(blob, source_ref=str(payload.get("name") or "upload.zip"), config=config)
    if source == "files":
        entries = payload.get("files")
        if not isinstance(entries, list) or not entries:
            raise ValueError("'files' must be a non-empty list of {path, content}.")
        files = {
            str(e["path"]): str(e.get("content") or "")
            for e in entries
            if isinstance(e, dict) and e.get("path")
        }
        if not files:
            raise ValueError("No usable file entries found.")
        return scan_files(files, source_ref=str(payload.get("name") or ""), config=config)
    raise ValueError(f"Unknown scan source: {source!r} (use github, zip, or files).")


def dump_result(result: CodeScanResult) -> str:
    return json.dumps(result.to_dict(), indent=2)
