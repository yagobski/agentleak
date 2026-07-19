"""Healthcare data detector: synthetic health identifiers (NAM-like),
diagnoses/conditions, and medications.

Kept intentionally simple (regex + dictionaries) per the V1 spec. The NAM-like
pattern is treated as *critical* because a government health-insurance number
is a direct, regulated re-identifier tied to medical records.

Note: the NAM-like pattern matches a synthetic shape only; it does not claim to
validate real Québec health-insurance numbers.
"""

from __future__ import annotations

import re

from ..core.detector import Detector, RawMatch, Severity

# Synthetic NAM shape: 4 letters + 8 digits (e.g. TREM12345678).
NAM_LIKE_RE = re.compile(r"\b[A-Z]{4}\d{8}\b")
# Same identifier written with spaces or hyphens between groups, optionally with
# an explicit ``NAM`` label (e.g. ``NAM TREM 8842 0197`` / ``TREM-8842-0197``).
# Kept separate from the tight form so the tight form's matched value (and its
# redaction) is unchanged.
NAM_SPACED_RE = re.compile(r"\b(?:NAM\s+)?[A-Z]{4}(?:[\s-]\d{2,4}){2,4}\b")
# US-style MRN / medical record number anchored on a keyword. Allows a leading
# ``NAM`` label and internal spaces/hyphens in the identifier body.
MRN_RE = re.compile(
    r"(?i)\b(?:mrn|medical record(?: number)?|health[_ ]?id)\b[:\s#]*"
    r"((?:NAM\s*)?[A-Z0-9][A-Z0-9 \-]{4,})"
)

HEALTH_CONDITIONS = [
    "diabetes", "cancer", "hypertension", "asthma", "depression", "anxiety",
    "pregnancy", "hiv", "aids", "hepatitis", "schizophrenia", "bipolar",
    "epilepsy", "alzheimer", "parkinson", "leukemia", "tumor", "stroke",
    # Oncology and other common clinical terms that realistic records use.
    "carcinoma", "colorectal", "melanoma", "lymphoma", "sarcoma", "metastatic",
    "myocardial infarction", "copd", "cirrhosis", "sclerosis", "psychosis",
    "diabète", "cancer du", "asthme", "dépression", "grossesse", "carcinome",
]

MEDICATIONS = [
    "insulin", "metformin", "chemotherapy", "morphine", "oxycodone",
    "antidepressant", "antiretroviral", "lithium", "warfarin", "prednisone",
    # Common chemotherapy agents and regimens found in oncology records.
    "folfox", "folfiri", "oxaliplatin", "5-fu", "fluorouracil", "cisplatin",
    "carboplatin", "paclitaxel", "docetaxel", "rituximab", "tamoxifen",
    "insuline", "chimiothérapie",
]


def _dictionary_regex(terms: list[str]) -> re.Pattern[str]:
    escaped = sorted({re.escape(t) for t in terms}, key=len, reverse=True)
    return re.compile(r"(?i)\b(" + "|".join(escaped) + r")\b")


_CONDITION_RE = _dictionary_regex(HEALTH_CONDITIONS)
_MEDICATION_RE = _dictionary_regex(MEDICATIONS)


class HealthcareDetector(Detector):
    name = "healthcare_detector"

    def detect(self, text: str) -> list[RawMatch]:
        matches: list[RawMatch] = []

        seen_ids: set[str] = set()
        for m in NAM_LIKE_RE.finditer(text):
            seen_ids.add(m.group(0))
            matches.append(self._match(
                data_type="health_identifier", severity=Severity.CRITICAL, confidence=0.85,
                matched_value=m.group(0),
                recommendation="Remove or mask health identifiers before calling external tools.",
            ))

        for m in NAM_SPACED_RE.finditer(text):
            value = m.group(0)
            # Don't double-report a tight identifier that also matched above.
            if value.replace(" ", "").replace("-", "").removeprefix("NAM") in {
                s for s in seen_ids
            } or value in seen_ids:
                continue
            matches.append(self._match(
                data_type="health_identifier", severity=Severity.CRITICAL, confidence=0.8,
                matched_value=value,
                recommendation="Remove or mask health identifiers before calling external tools.",
            ))

        for m in MRN_RE.finditer(text):
            matches.append(self._match(
                data_type="health_identifier", severity=Severity.CRITICAL, confidence=0.8,
                matched_value=m.group(1),
                recommendation="Remove or mask medical record numbers before internal channels.",
            ))

        for m in _CONDITION_RE.finditer(text):
            matches.append(self._match(
                data_type="health_condition", severity=Severity.MEDIUM, confidence=0.7,
                matched_value=m.group(1),
                recommendation="Avoid restating specific diagnoses in channels that don't need them.",
            ))

        for m in _MEDICATION_RE.finditer(text):
            matches.append(self._match(
                data_type="medication", severity=Severity.MEDIUM, confidence=0.65,
                matched_value=m.group(1),
                recommendation="Medication details reveal conditions; share only with authorized agents.",
            ))

        return matches
