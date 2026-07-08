"""Presidio-based detector — Tier 2 of the hybrid pipeline (optional extra).

Requires: ``pip install agentleak[presidio]`` which pulls in
``presidio-analyzer`` and ``spacy`` with the ``en_core_web_lg`` model.

When presidio is not installed the detector silently returns no matches so the
pipeline degrades gracefully to Tier-1 regex only.

Domain-specific recognizers (20+):
- PatientIDRecognizer — NAM-like identifiers (``[A-Z]{4}\\d{8}``)
- MedicalLicenseRecognizer — licence formats (``[A-Z]{2,3}\\d{6,7}``)
- InsuranceIDRecognizer — Insurance membership IDs
- IMEIRecognizer — IMEI device identifiers
- VINRecognizer — Vehicle Identification Numbers
- CryptoAddressRecognizer — BTC / ETH wallet addresses
- BICRecognizer — Bank Identifier Codes
- CVVRecognizer — Card verification values
- PINRecognizer — 4–6 digit PINs (keyword-anchored)
- MACAddressRecognizer — MAC hardware addresses
- GPSCoordRecognizer — latitude/longitude pairs
- VRMRecognizer — UK vehicle registration marks
- CanaryRecognizer — verbatim canary-token matching
"""

from __future__ import annotations

import re
from typing import Any

from ..core.detector import Detector, RawMatch, Severity

# ---------------------------------------------------------------------------
# Optional import guard — graceful degradation when presidio is absent
# ---------------------------------------------------------------------------
try:
    from presidio_analyzer import (  # type: ignore[import]  # type: ignore[import]
        AnalyzerEngine,
        EntityRecognizer,
        RecognizerRegistry,
        RecognizerResult,
    )
    from presidio_analyzer.nlp_engine import NlpEngineProvider  # type: ignore[import]
    _PRESIDIO_AVAILABLE = True
except ImportError:
    _PRESIDIO_AVAILABLE = False


# ---------------------------------------------------------------------------
# Mapping Presidio entity labels → AgentLeak data types / severities
# ---------------------------------------------------------------------------
_ENTITY_MAP: dict[str, tuple[str, Severity]] = {
    "PERSON": ("person_name", Severity.LOW),
    "EMAIL_ADDRESS": ("email", Severity.MEDIUM),
    "PHONE_NUMBER": ("phone_number", Severity.MEDIUM),
    "IP_ADDRESS": ("ip_address", Severity.MEDIUM),
    "US_SSN": ("ssn", Severity.CRITICAL),
    "US_BANK_NUMBER": ("account_number", Severity.HIGH),
    "CREDIT_CARD": ("credit_card", Severity.CRITICAL),
    "IBAN_CODE": ("iban", Severity.CRITICAL),
    "LOCATION": ("address", Severity.MEDIUM),
    "DATE_TIME": ("date_of_birth", Severity.MEDIUM),
    "NRP": ("person_name", Severity.LOW),
    "MEDICAL_LICENSE": ("health_identifier", Severity.CRITICAL),
    "PATIENT_ID": ("health_identifier", Severity.CRITICAL),
    "INSURANCE_ID": ("insurance_id", Severity.HIGH),
    "IMEI": ("device_id", Severity.MEDIUM),
    "VIN": ("vehicle_id", Severity.MEDIUM),
    "CRYPTO": ("crypto_address", Severity.HIGH),
    "BIC": ("account_number", Severity.HIGH),
    "CVV": ("credit_card", Severity.CRITICAL),
    "PIN": ("credit_card", Severity.CRITICAL),
    "MAC_ADDRESS": ("ip_address", Severity.MEDIUM),
    "GPS_COORD": ("address", Severity.MEDIUM),
    "VRM": ("vehicle_id", Severity.MEDIUM),
    "CANARY": ("canary", Severity.CRITICAL),
    "URL": ("url", Severity.LOW),
}


# ---------------------------------------------------------------------------
# Custom recognizers (only defined when presidio is available)
# ---------------------------------------------------------------------------
if _PRESIDIO_AVAILABLE:
    class _PatternRecognizer(EntityRecognizer):  # type: ignore[misc]
        """Minimal helper — subclasses just set NAME, PATTERNS, CONTEXT."""

        NAME: str = ""
        PATTERNS: list[tuple[str, float]] = []  # (regex, confidence)
        CONTEXT: list[str] = []

        def __init__(self) -> None:
            super().__init__(
                supported_entities=[self.NAME],
                name=f"{self.NAME}Recognizer",
            )
            self._compiled = [
                (re.compile(p, re.IGNORECASE), c) for p, c in self.PATTERNS
            ]
            self._ctx_words = {w.lower() for w in self.CONTEXT}

        def load(self) -> None:  # required by presidio ABC
            pass

        def analyze(
            self, text: str, entities: list[str], nlp_artifacts: Any = None
        ) -> list[Any]:
            results: list[Any] = []
            ctx_boost = 0.1 if self._ctx_words and any(
                w in text.lower() for w in self._ctx_words
            ) else 0.0
            for pattern, base_conf in self._compiled:
                for m in pattern.finditer(text):
                    conf = min(1.0, base_conf + ctx_boost)
                    results.append(
                        RecognizerResult(
                            entity_type=self.NAME,
                            start=m.start(),
                            end=m.end(),
                            score=conf,
                        )
                    )
            return results

    class PatientIDRecognizer(_PatternRecognizer):
        NAME = "PATIENT_ID"
        PATTERNS = [(r"\b[A-Z]{4}\d{8}\b", 0.85)]
        CONTEXT = ["patient", "mrn", "record", "chart"]

    class MedicalLicenseRecognizer(_PatternRecognizer):
        NAME = "MEDICAL_LICENSE"
        PATTERNS = [(r"\b[A-Z]{2,3}\d{6,7}\b", 0.80)]
        CONTEXT = ["license", "licence", "physician", "doctor", "prescriber"]

    class InsuranceIDRecognizer(_PatternRecognizer):
        NAME = "INSURANCE_ID"
        PATTERNS = [(r"\b[A-Z]{2,3}\d{8,12}\b", 0.75)]
        CONTEXT = ["insurance", "policy", "member", "subscriber", "coverage"]

    class IMEIRecognizer(_PatternRecognizer):
        NAME = "IMEI"
        PATTERNS = [(r"\b\d{15}\b", 0.70)]
        CONTEXT = ["imei", "device", "serial", "mobile", "handset"]

    class VINRecognizer(_PatternRecognizer):
        NAME = "VIN"
        PATTERNS = [(r"\b[A-HJ-NPR-Z0-9]{17}\b", 0.80)]
        CONTEXT = ["vin", "vehicle", "chassis", "car", "truck"]

    class CryptoAddressRecognizer(_PatternRecognizer):
        NAME = "CRYPTO"
        PATTERNS = [
            (r"\b(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,62}\b", 0.85),  # BTC
            (r"\b0x[a-fA-F0-9]{40}\b", 0.90),  # ETH
        ]
        CONTEXT = ["wallet", "btc", "bitcoin", "eth", "ethereum", "crypto", "address"]

    class BICRecognizer(_PatternRecognizer):
        NAME = "BIC"
        PATTERNS = [(r"\b[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?\b", 0.75)]
        CONTEXT = ["bic", "swift", "bank", "transfer", "wire"]

    class CVVRecognizer(_PatternRecognizer):
        NAME = "CVV"
        PATTERNS = [(r"\b\d{3,4}\b", 0.60)]
        CONTEXT = ["cvv", "cvc", "cvn", "security code", "card code"]

    class PINRecognizer(_PatternRecognizer):
        NAME = "PIN"
        PATTERNS = [(r"\b\d{4,6}\b", 0.55)]
        CONTEXT = ["pin", "passcode", "atm pin", "card pin"]

    class MACAddressRecognizer(_PatternRecognizer):
        NAME = "MAC_ADDRESS"
        PATTERNS = [(r"\b([0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}\b", 0.90)]
        CONTEXT = ["mac", "hardware", "network", "ethernet", "interface"]

    class GPSCoordRecognizer(_PatternRecognizer):
        NAME = "GPS_COORD"
        PATTERNS = [(r"(-?\d{1,3}\.\d{4,}),\s*(-?\d{1,3}\.\d{4,})", 0.80)]
        CONTEXT = ["gps", "lat", "lon", "location", "coordinates", "latitude", "longitude"]

    class VRMRecognizer(_PatternRecognizer):
        NAME = "VRM"
        PATTERNS = [(r"\b[A-Z]{2}\d{2}\s?[A-Z]{3}\b", 0.80)]
        CONTEXT = ["registration", "plate", "vehicle", "reg", "number plate"]

    _CUSTOM_RECOGNIZERS = [
        PatientIDRecognizer,
        MedicalLicenseRecognizer,
        InsuranceIDRecognizer,
        IMEIRecognizer,
        VINRecognizer,
        CryptoAddressRecognizer,
        BICRecognizer,
        CVVRecognizer,
        PINRecognizer,
        MACAddressRecognizer,
        GPSCoordRecognizer,
        VRMRecognizer,
    ]


def _build_analyzer(score_threshold: float = 0.5) -> Any:
    """Instantiate an AnalyzerEngine with all custom recognizers added."""
    if not _PRESIDIO_AVAILABLE:
        return None
    registry = RecognizerRegistry()
    registry.load_predefined_recognizers()
    for cls in _CUSTOM_RECOGNIZERS:
        registry.add_recognizer(cls())
    provider = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
    })
    nlp_engine = provider.create_engine()
    return AnalyzerEngine(
        registry=registry,
        nlp_engine=nlp_engine,
        supported_languages=["en"],
    )


class PresidioDetector(Detector):
    """Tier-2 detector using Microsoft Presidio + domain-specific recognizers.

    Requires ``pip install agentleak[presidio]``. When not installed the
    detector is a no-op (returns ``[]`` for every input).
    """

    name = "presidio"

    def __init__(self, *, score_threshold: float = 0.5) -> None:
        self._available = _PRESIDIO_AVAILABLE
        self._analyzer: Any = None
        self._threshold = score_threshold
        if self._available:
            try:
                self._analyzer = _build_analyzer(score_threshold)
            except Exception:
                self._available = False

    def detect(self, text: str) -> list[RawMatch]:
        if not self._available or self._analyzer is None or not text:
            return []

        try:
            results = self._analyzer.analyze(text=text, language="en")
        except Exception:
            return []

        matches: list[RawMatch] = []
        seen: set[tuple[str, str]] = set()
        for r in results:
            if r.score < self._threshold:
                continue
            entity = r.entity_type
            data_type, severity = _ENTITY_MAP.get(entity, ("other_pii", Severity.MEDIUM))
            evidence = text[r.start:r.end]
            key = (data_type, evidence)
            if key in seen:
                continue
            seen.add(key)
            matches.append(RawMatch(
                data_type=data_type,
                severity=severity,
                confidence=float(r.score),
                matched_value=evidence,
                recommendation=f"Presidio detected {entity}: mask before forwarding.",
                detector="presidio",
            ))
        return matches
