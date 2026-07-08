"""General PII detector: emails, phones, SSN/SIN, credit cards, IPs, DOB,
client identifiers, and keyword-anchored probable names.

Patterns favor precision over recall and attach a per-pattern confidence so
the scoring engine can weigh noisy matches (phones, names) less than crisp
ones (emails, validated cards).
"""

from __future__ import annotations

import re

from ..core.detector import Detector, RawMatch, Severity

EMAIL_RE = re.compile(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9-.]+")
# US SSN (xxx-xx-xxxx) and Canadian SIN (xxx-xxx-xxx) are distinct shapes.
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
SIN_RE = re.compile(r"\b\d{3}[- ]\d{3}[- ]\d{3}\b")
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]\d{3}[-.\s]\d{4}(?!\d)"
)
IP_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
# IPv6 in expanded/partly-compressed form. Requires at least four groups so we
# never mistake a clock time (12:34:56) for an address; precision over recall.
IPV6_RE = re.compile(
    r"\b(?:[A-Fa-f0-9]{1,4}:){3,7}[A-Fa-f0-9]{1,4}\b"
    r"|\b(?:[A-Fa-f0-9]{1,4}:){1,6}:[A-Fa-f0-9]{1,4}\b"
)
# IPv4 that is actually a software version ("version 1.2.3.4") is not a client
# IP leak — used to suppress that false positive.
_VERSION_PREFIX_RE = re.compile(r"\b(?:version|ver|build|release|rev)\b[\s:v.]*$", re.IGNORECASE)
CREDIT_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,16}\b")
# Dates only flagged as DOB when anchored to a birth keyword (avoids matching
# trace timestamps and arbitrary dates).
DOB_RE = re.compile(
    r"(?i)\b(?:dob|d\.o\.b\.|date of birth|born|birth ?date)\b[:\s]*"
    r"(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
)
CLIENT_ID_RE = re.compile(r"\b(?:ACC|ACCT|CUST|CLIENT|USER|MEMBER)[-_]?\d{3,}\b", re.IGNORECASE)
# UK National Insurance Number (AB123456C). Uses the official valid-prefix rules
# (excludes administrative prefixes like BG/GB/NK/ZZ and the letters D/F/I/Q/U/V)
# so the shape is distinctive enough to match without a keyword.
NINO_RE = re.compile(
    r"\b(?!BG|GB|NK|KN|TN|NT|ZZ)"
    r"[ABCEGHJ-PRSTW-Z][ABCEGHJ-NPRSTW-Z]\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b"
)
# Street address: number + street words + a street-type suffix.
ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+(?:[A-Z][A-Za-z.]+\s){1,3}"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Way|Place|Pl)\b\.?",
    re.IGNORECASE,
)
# French / Québec civic address: number + street-type word *before* the name
# (e.g. "1240 Rue Saint-Denis", "85 Boulevard René-Lévesque"). Grounded in
# Law 25 — Québec addresses don't use the English "<name> Street" suffix shape.
ADDRESS_FR_RE = re.compile(
    r"\b\d{1,5}(?:[-\s]\d{1,4})?\s+"
    r"(?:Rue|Avenue|Av|Boulevard|Boul|Bd|Chemin|Ch|C[ôo]te|Place|All[ée]e|"
    r"Impasse|Mont[ée]e|Rang|Croissant|Promenade|Terrasse|Carr[ée])\.?\s+"
    r"[A-ZÀ-Ý][\wÀ-ÿ'’.-]+(?:[ -][A-ZÀ-Ý][\wÀ-ÿ'’.-]+){0,3}",
    re.IGNORECASE,
)
# Canadian postal code (A1A 1A1) — distinctive enough to match without a keyword.
POSTAL_RE = re.compile(r"\b[A-Za-z]\d[A-Za-z][ -]?\d[A-Za-z]\d\b")
# Probable full name following a person keyword, e.g. "patient Jean Tremblay".
# The keyword is case-insensitive (scoped flag) but the captured name must be
# properly capitalized — a global (?i) would let it swallow trailing lowercase
# words like "Jean Tremblay has".
NAME_RE = re.compile(
    r"\b(?i:patient|client|customer|employee|name|mr|mrs|ms|dr|prof)\b"
    r"[\"'\s:_]+([A-ZÀ-Ý][a-zà-ÿ]+(?:[ -][A-ZÀ-Ý][a-zà-ÿ]+){1,2})"
)


def _luhn_ok(digits: str) -> bool:
    nums = [int(d) for d in digits if d.isdigit()]
    if not 13 <= len(nums) <= 16:
        return False
    total = 0
    for i, n in enumerate(reversed(nums)):
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


class PIIDetector(Detector):
    name = "pii_detector"

    def detect(self, text: str) -> list[RawMatch]:
        matches: list[RawMatch] = []

        for m in EMAIL_RE.finditer(text):
            matches.append(self._match(
                data_type="email", severity=Severity.MEDIUM, confidence=0.95,
                matched_value=m.group(0),
                recommendation="Mask email addresses before internal channels and logs.",
            ))

        for m in SSN_RE.finditer(text):
            matches.append(self._match(
                data_type="ssn", severity=Severity.HIGH, confidence=0.85,
                matched_value=m.group(0),
                recommendation="Never transmit full social security numbers; tokenize them.",
            ))

        for m in SIN_RE.finditer(text):
            matches.append(self._match(
                data_type="sin", severity=Severity.HIGH, confidence=0.8,
                matched_value=m.group(0),
                recommendation="Never transmit full social insurance numbers; tokenize them.",
            ))

        for m in PHONE_RE.finditer(text):
            matches.append(self._match(
                data_type="phone_number", severity=Severity.MEDIUM, confidence=0.65,
                matched_value=m.group(0).strip(),
                recommendation="Avoid sending full phone numbers to tools and logs.",
            ))

        for m in CREDIT_CARD_RE.finditer(text):
            raw = m.group(0)
            if _luhn_ok(raw):
                matches.append(self._match(
                    data_type="credit_card", severity=Severity.HIGH, confidence=0.95,
                    matched_value=raw.strip(),
                    recommendation="Card numbers must never appear in agent channels; use a vault token.",
                ))

        for m in IP_RE.finditer(text):
            # Skip version strings like "version 1.2.3.4" — not a client IP.
            if _VERSION_PREFIX_RE.search(text[max(0, m.start() - 16):m.start()]):
                continue
            matches.append(self._match(
                data_type="ip_address", severity=Severity.LOW, confidence=0.6,
                matched_value=m.group(0),
                recommendation="Strip client IP addresses from internal traces where not required.",
            ))

        for m in IPV6_RE.finditer(text):
            matches.append(self._match(
                data_type="ip_address", severity=Severity.LOW, confidence=0.6,
                matched_value=m.group(0),
                recommendation="Strip client IP addresses from internal traces where not required.",
            ))

        for m in DOB_RE.finditer(text):
            matches.append(self._match(
                data_type="date_of_birth", severity=Severity.MEDIUM, confidence=0.75,
                matched_value=m.group(1),
                recommendation="Generalize dates of birth (e.g. to year) instead of passing exact values.",
            ))

        for m in CLIENT_ID_RE.finditer(text):
            matches.append(self._match(
                data_type="client_identifier", severity=Severity.MEDIUM, confidence=0.7,
                matched_value=m.group(0),
                recommendation="Use opaque, scoped identifiers instead of raw client/account ids.",
            ))

        for m in NINO_RE.finditer(text):
            matches.append(self._match(
                data_type="national_insurance_number", severity=Severity.HIGH, confidence=0.8,
                matched_value=m.group(0),
                recommendation="Never transmit full National Insurance numbers; tokenize them.",
            ))

        for m in NAME_RE.finditer(text):
            matches.append(self._match(
                data_type="person_name", severity=Severity.MEDIUM, confidence=0.55,
                matched_value=m.group(1),
                recommendation="Minimize full names passed between agents; prefer references.",
            ))

        for m in ADDRESS_RE.finditer(text):
            matches.append(self._match(
                data_type="address", severity=Severity.HIGH, confidence=0.7,
                matched_value=m.group(0).strip(),
                recommendation="Home addresses are re-identifying; remove them from internal channels.",
            ))

        for m in ADDRESS_FR_RE.finditer(text):
            matches.append(self._match(
                data_type="address", severity=Severity.HIGH, confidence=0.7,
                matched_value=m.group(0).strip(),
                recommendation="Home addresses are re-identifying; remove them from internal channels.",
            ))

        for m in POSTAL_RE.finditer(text):
            matches.append(self._match(
                data_type="address", severity=Severity.MEDIUM, confidence=0.6,
                matched_value=m.group(0),
                recommendation="Postal codes narrow identity; avoid passing them where not required.",
            ))

        return matches
